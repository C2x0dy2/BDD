from django.db import connection


def _run(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def sales_by_category():
    """Reads directly from the category_sales_view (JOIN + GROUP BY baked
    into the view definition in docker/init-sql/01_schema.sql)."""
    return _run("SELECT * FROM category_sales_view ORDER BY revenue DESC")


def top_selling_products(limit=10):
    """Inner join across products / order_items / orders, aggregated and
    ranked by revenue from paid or shipped orders."""
    sql = """
        SELECT
            p.id,
            p.name,
            p.sku,
            SUM(oi.quantity) AS units_sold,
            SUM(oi.quantity * oi.unit_price) AS revenue
        FROM products p
        INNER JOIN order_items oi ON oi.product_id = p.id
        INNER JOIN orders o ON o.id = oi.order_id
        WHERE o.status IN ('paid', 'shipped')
        GROUP BY p.id, p.name, p.sku
        ORDER BY revenue DESC
        LIMIT %s
    """
    return _run(sql, [limit])


def categories_with_product_counts():
    """Left (outer) join: every category is returned, including those
    with zero products, unlike an inner join which would drop them."""
    sql = """
        SELECT c.id, c.name, COUNT(p.id) AS product_count
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.id
        GROUP BY c.id, c.name
        ORDER BY product_count DESC
    """
    return _run(sql)


def frequent_customers(min_orders=3):
    """GROUP BY / HAVING: customers who placed more than `min_orders`
    orders."""
    sql = """
        SELECT cu.id, cu.email, COUNT(o.id) AS order_count
        FROM customers cu
        JOIN orders o ON o.customer_id = cu.id
        GROUP BY cu.id, cu.email
        HAVING COUNT(o.id) > %s
        ORDER BY order_count DESC
    """
    return _run(sql, [min_orders])


def customers_without_orders():
    """NOT EXISTS subquery: customers who have never placed an order."""
    sql = """
        SELECT cu.id, cu.email, cu.first_name, cu.last_name
        FROM customers cu
        WHERE NOT EXISTS (
            SELECT 1 FROM orders o WHERE o.customer_id = cu.id
        )
        ORDER BY cu.id
    """
    return _run(sql)


def monthly_revenue():
    """CTE + window function: monthly revenue from paid/shipped orders,
    with a running cumulative total computed via SUM() OVER."""
    sql = """
        WITH monthly AS (
            SELECT
                date_trunc('month', o.created_at) AS month,
                SUM(oi.quantity * oi.unit_price) AS revenue
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.id
            WHERE o.status IN ('paid', 'shipped')
            GROUP BY date_trunc('month', o.created_at)
        )
        SELECT
            month,
            revenue,
            SUM(revenue) OVER (ORDER BY month) AS cumulative_revenue
        FROM monthly
        ORDER BY month
    """
    return _run(sql)


def order_status_breakdown():
    """Aggregate FILTER clause: counts and revenue split by status in a
    single pass over orders, instead of one query per status."""
    sql = """
        SELECT
            COUNT(*) AS total_orders,
            COUNT(*) FILTER (WHERE status = 'pending') AS pending_count,
            COUNT(*) FILTER (WHERE status = 'paid') AS paid_count,
            COUNT(*) FILTER (WHERE status = 'shipped') AS shipped_count,
            COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_count,
            COALESCE(SUM(total_amount) FILTER (WHERE status IN ('paid', 'shipped')), 0) AS confirmed_revenue
        FROM orders
    """
    return _run(sql)
