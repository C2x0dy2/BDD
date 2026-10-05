-- Relational schema for the e-commerce project (PostgreSQL).
-- Executed once, automatically, by the official postgres image on first
-- container start (docker-entrypoint-initdb.d), as the bootstrap superuser
-- defined by POSTGRES_USER/POSTGRES_PASSWORD.
--
-- Django never runs migrations against these tables (models are
-- `managed = False`): this script is the single source of truth for the
-- schema, constraints, view, index, and trigger.

-- ---------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------

CREATE TABLE categories (
    id    BIGSERIAL PRIMARY KEY,
    name  VARCHAR(100) NOT NULL UNIQUE,
    slug  VARCHAR(120) NOT NULL UNIQUE
);

CREATE TABLE products (
    id              BIGSERIAL PRIMARY KEY,
    sku             VARCHAR(32)  NOT NULL UNIQUE,
    name            VARCHAR(200) NOT NULL,
    category_id     BIGINT NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    price           NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    stock_quantity  INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE customers (
    id          BIGSERIAL PRIMARY KEY,
    email       VARCHAR(254) NOT NULL UNIQUE,
    first_name  VARCHAR(100) NOT NULL,
    last_name   VARCHAR(100) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE orders (
    id            BIGSERIAL PRIMARY KEY,
    customer_id   BIGINT NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    status        VARCHAR(20) NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'paid', 'shipped', 'cancelled')),
    total_amount  NUMERIC(12, 2) NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE order_items (
    id          BIGSERIAL PRIMARY KEY,
    order_id    BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id  BIGINT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity    INTEGER NOT NULL CHECK (quantity > 0),
    unit_price  NUMERIC(10, 2) NOT NULL,
    UNIQUE (order_id, product_id)
);

-- ---------------------------------------------------------------------
-- View: revenue, quantity sold, and catalog size per category.
-- Used by GET /api/reports/sales-by-category/.
-- ---------------------------------------------------------------------

CREATE VIEW category_sales_view AS
SELECT
    c.id                                        AS category_id,
    c.name                                       AS category_name,
    COUNT(DISTINCT p.id)                         AS product_count,
    COALESCE(SUM(oi.quantity), 0)                AS units_sold,
    COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS revenue
FROM categories c
LEFT JOIN products p ON p.category_id = c.id
LEFT JOIN order_items oi ON oi.product_id = p.id
LEFT JOIN orders o ON o.id = oi.order_id AND o.status IN ('paid', 'shipped')
GROUP BY c.id, c.name;

-- ---------------------------------------------------------------------
-- Index: order_items is looked up heavily by product_id (revenue-by-product
-- reports, "which orders contain product X"). Measured before/after with
-- EXPLAIN (ANALYZE) in docs/presentation.md section 7.
-- ---------------------------------------------------------------------

CREATE INDEX idx_order_items_product_id ON order_items (product_id);

-- ---------------------------------------------------------------------
-- Trigger + function: keep orders.total_amount consistent with its items
-- without relying on application code to recompute it.
-- ---------------------------------------------------------------------

CREATE OR REPLACE FUNCTION recalc_order_total() RETURNS TRIGGER AS $$
DECLARE
    affected_order_id BIGINT;
BEGIN
    affected_order_id := COALESCE(NEW.order_id, OLD.order_id);

    UPDATE orders
    SET total_amount = (
        SELECT COALESCE(SUM(quantity * unit_price), 0)
        FROM order_items
        WHERE order_id = affected_order_id
    )
    WHERE id = affected_order_id;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_recalc_order_total
AFTER INSERT OR UPDATE OR DELETE ON order_items
FOR EACH ROW
EXECUTE FUNCTION recalc_order_total();

-- ---------------------------------------------------------------------
-- Restricted application role: the Django API connects as this role, never
-- as the bootstrap superuser. DML only, no DDL, no ownership.
--
-- Demo credentials for a student project -- not meant for production use.
-- ---------------------------------------------------------------------

CREATE ROLE commerce_app LOGIN PASSWORD 'commerce_app_pw';

GRANT CONNECT ON DATABASE commerce TO commerce_app;
GRANT USAGE ON SCHEMA public TO commerce_app;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON categories, products, customers, orders, order_items
    TO commerce_app;
GRANT SELECT ON category_sales_view TO commerce_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO commerce_app;
