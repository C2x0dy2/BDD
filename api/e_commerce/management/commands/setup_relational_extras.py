"""
Creates the relational-DB extras the EFREI BDD subject asks for, on top of
the tables already created by `manage.py migrate --database=migration`:
a view, a deliberately-created index, a trigger+function, an extra CHECK
constraint, and the restricted `commerce_app` role the application connects
with at runtime (never the migration/owner role).

Idempotent: safe to run on every container start (uses CREATE OR REPLACE /
IF NOT EXISTS / DROP-then-ADD everywhere).

Must run against the 'migration' database alias (owner role with DDL
rights) -- the 'default' alias (commerce_app) intentionally cannot do DDL.
"""
import os

from django.core.management.base import BaseCommand
from django.db import connections

SQL = """
-- Superseded by idx_order_created_at below: the first one duplicated the
-- index Django already auto-creates on every FK column, and the second
-- (payment_status) wasn't selective enough for the planner to ever prefer
-- it over a sequential scan on this table size (~60% of rows match
-- 'paid'). created_at is a better fit.
DROP INDEX IF EXISTS idx_orderitem_product_id;
DROP INDEX IF EXISTS idx_order_payment_status;

-- View: revenue, units sold, and catalog size per category (paid orders
-- only). Used by GET /api/reports/sales-by-category/.
CREATE OR REPLACE VIEW category_sales_view AS
SELECT
    c.id AS category_id,
    c.name AS category_name,
    COUNT(DISTINCT p.id) AS product_count,
    COALESCE(SUM(oi.quantity), 0) AS units_sold,
    COALESCE(SUM(oi.quantity * oi.price), 0) AS revenue
FROM e_commerce_category c
LEFT JOIN e_commerce_product p ON p.category_id = c.id
LEFT JOIN e_commerce_orderitem oi ON oi.product_id = p.id
LEFT JOIN e_commerce_order o ON o.id = oi.order_id AND o.payment_status = 'paid'
GROUP BY c.id, c.name;

-- Index: date-range lookups on orders (recent-orders dashboards, monthly
-- reporting) filter on created_at, which -- unlike product_id/order_id/
-- user_id/category_id -- is not a foreign key, so Django does not index
-- it automatically. High-cardinality timestamp column, so (unlike a
-- low-cardinality status flag) the planner actually prefers the index
-- over a sequential scan. Measured before/after with EXPLAIN (ANALYZE)
-- in docs/presentation.md.
CREATE INDEX IF NOT EXISTS idx_order_created_at
    ON e_commerce_order (created_at);

-- Extra CHECK constraint (on top of the ones Django already generates for
-- PositiveIntegerField columns like stock/quantity): price can't be
-- negative.
ALTER TABLE e_commerce_product DROP CONSTRAINT IF EXISTS product_price_non_negative;
ALTER TABLE e_commerce_product ADD CONSTRAINT product_price_non_negative CHECK (price >= 0);

-- Trigger + function: keep orders.total_amount consistent with its items
-- without relying on application code to recompute it.
CREATE OR REPLACE FUNCTION recalc_order_total() RETURNS TRIGGER AS $$
DECLARE
    affected_order_id BIGINT;
BEGIN
    affected_order_id := COALESCE(NEW.order_id, OLD.order_id);

    UPDATE e_commerce_order
    SET total_amount = (
        SELECT COALESCE(SUM(quantity * price), 0)
        FROM e_commerce_orderitem
        WHERE order_id = affected_order_id
    )
    WHERE id = affected_order_id;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_recalc_order_total ON e_commerce_orderitem;
CREATE TRIGGER trg_recalc_order_total
AFTER INSERT OR UPDATE OR DELETE ON e_commerce_orderitem
FOR EACH ROW
EXECUTE FUNCTION recalc_order_total();

-- Restricted application role: the Django API connects as this role at
-- runtime (settings.DATABASES['default']), never as the bootstrap owner
-- used for migrate/this command. DML only, no DDL, no ownership.
-- The password is set separately in handle() from the environment, so no
-- secret lives in this file.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'commerce_app') THEN
        CREATE ROLE commerce_app LOGIN;
    END IF;
END
$$;

GRANT CONNECT ON DATABASE sika TO commerce_app;
GRANT USAGE ON SCHEMA public TO commerce_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO commerce_app;
GRANT SELECT ON category_sales_view TO commerce_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO commerce_app;
"""


class Command(BaseCommand):
    help = "Create the view/index/trigger/CHECK/restricted role on top of the Django-migrated schema."

    def handle(self, *args, **options):
        connection = connections["migration"]
        with connection.cursor() as cursor:
            cursor.execute(SQL)
            # Role names cannot be bound as parameters, but the password
            # literal can; it is rebuilt from the env on every start so a
            # rotated .env value takes effect.
            cursor.execute(
                "SELECT format('ALTER ROLE commerce_app PASSWORD %%L', %s)",
                [os.environ["POSTGRES_APP_PASSWORD"]],
            )
            cursor.execute(cursor.fetchone()[0])
        self.stdout.write(self.style.SUCCESS(
            "setup_relational_extras: view, index, trigger, constraint and commerce_app role are in place."
        ))
