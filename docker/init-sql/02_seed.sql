-- Demo dataset: a few thousand rows per table so joins/aggregates/EXPLAIN
-- comparisons are meaningful. Runs once, right after 01_schema.sql, as the
-- bootstrap superuser (which still owns/can write to every table at this
-- point, before commerce_app's restricted grants matter for seeding).

SELECT setseed(0.42);

-- ---------------------------------------------------------------------
-- Categories (fixed list, used by product generation below)
-- ---------------------------------------------------------------------

INSERT INTO categories (name, slug) VALUES
    ('Electronics', 'electronics'),
    ('Books', 'books'),
    ('Clothing', 'clothing'),
    ('Home & Kitchen', 'home-kitchen'),
    ('Sports & Outdoors', 'sports-outdoors'),
    ('Toys & Games', 'toys-games'),
    ('Beauty', 'beauty'),
    ('Garden', 'garden'),
    ('Automotive', 'automotive'),
    ('Grocery', 'grocery');

-- ---------------------------------------------------------------------
-- Products: 2,000 rows spread across the 10 categories.
-- ---------------------------------------------------------------------

INSERT INTO products (sku, name, category_id, price, stock_quantity, created_at)
SELECT
    'SKU-' || LPAD(s::text, 6, '0'),
    c.name || ' Product ' || s,
    c.id,
    ROUND((5 + random() * 495)::numeric, 2),
    FLOOR(random() * 200)::int,
    now() - (random() * interval '365 days')
FROM generate_series(1, 2000) AS s
JOIN categories c ON c.id = 1 + (s % 10);

-- ---------------------------------------------------------------------
-- Customers: 1,500 rows.
-- ---------------------------------------------------------------------

INSERT INTO customers (email, first_name, last_name, created_at)
SELECT
    'customer' || s || '@example.com',
    'FirstName' || s,
    'LastName' || s,
    now() - (random() * interval '365 days')
FROM generate_series(1, 1500) AS s;

-- ---------------------------------------------------------------------
-- Orders: 3,000 rows, random customer/status/date.
-- ---------------------------------------------------------------------

INSERT INTO orders (customer_id, status, created_at)
SELECT
    1 + FLOOR(random() * 1500)::int,
    (ARRAY['pending', 'paid', 'shipped', 'cancelled'])[1 + FLOOR(random() * 4)::int],
    now() - (random() * interval '365 days')
FROM generate_series(1, 3000) AS s;

-- ---------------------------------------------------------------------
-- Order items: 1 to 4 items per order (~7,500 rows), each referencing a
-- random product at its current price. The trg_recalc_order_total trigger
-- fires per row and leaves orders.total_amount consistent automatically.
-- ---------------------------------------------------------------------

INSERT INTO order_items (order_id, product_id, quantity, unit_price)
SELECT
    o.id,
    p.id,
    1 + FLOOR(random() * 5)::int,
    p.price
FROM orders o
CROSS JOIN LATERAL (
    -- md5(o.id || p2.id) correlates the subquery with the outer order row
    -- (o.id), forcing PostgreSQL to re-run it per order instead of hoisting
    -- an uncorrelated "ORDER BY random() LIMIT n" once for every order.
    SELECT p2.id, p2.price
    FROM products p2
    ORDER BY md5(o.id::text || '-' || p2.id::text)
    LIMIT 1 + (o.id % 4)
) AS p
ON CONFLICT (order_id, product_id) DO NOTHING;
