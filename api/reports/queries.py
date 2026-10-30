from django.db import connection

# SIKA's Django-managed tables (see e_commerce/models.py); names follow
# Django's default <app_label>_<model> convention, confirmed against the
# actual schema created by `manage.py migrate --database=migration`.
CATEGORIES = "e_commerce_category"
PRODUCTS = "e_commerce_product"
USERS = "e_commerce_user"
ORDERS = "e_commerce_order"
ORDER_ITEMS = "e_commerce_orderitem"


def _run(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def sales_by_category():
    """Reads directly from the category_sales_view (JOIN + GROUP BY baked
    into the view definition, created by setup_relational_extras)."""
    return _run("SELECT * FROM category_sales_view ORDER BY revenue DESC")


def top_selling_products(limit=10):
    """Inner join across products / order items / orders, aggregated and
    ranked by revenue from paid orders."""
    sql = f"""
        SELECT
            p.id,
            p.name,
            p.slug,
            SUM(oi.quantity) AS units_sold,
            SUM(oi.quantity * oi.price) AS revenue
        FROM {PRODUCTS} p
        INNER JOIN {ORDER_ITEMS} oi ON oi.product_id = p.id
        INNER JOIN {ORDERS} o ON o.id = oi.order_id
        WHERE o.payment_status = 'paid'
        GROUP BY p.id, p.name, p.slug
        ORDER BY revenue DESC
        LIMIT %s
    """
    return _run(sql, [limit])


def categories_with_product_counts():
    """Left (outer) join: every category is returned, including those
    with zero products, unlike an inner join which would drop them."""
    sql = f"""
        SELECT c.id, c.name, COUNT(p.id) AS product_count
        FROM {CATEGORIES} c
        LEFT JOIN {PRODUCTS} p ON p.category_id = c.id
        GROUP BY c.id, c.name
        ORDER BY product_count DESC
    """
    return _run(sql)


def frequent_customers(min_orders=3):
    """GROUP BY / HAVING: users who placed more than `min_orders` orders."""
    sql = f"""
        SELECT u.id, u.email, u.username, COUNT(o.id) AS order_count
        FROM {USERS} u
        JOIN {ORDERS} o ON o.user_id = u.id
        GROUP BY u.id, u.email, u.username
        HAVING COUNT(o.id) > %s
        ORDER BY order_count DESC
    """
    return _run(sql, [min_orders])


def customers_without_orders():
    """NOT EXISTS subquery: users who have never placed an order."""
    sql = f"""
        SELECT u.id, u.email, u.username, u.first_name, u.last_name
        FROM {USERS} u
        WHERE NOT EXISTS (
            SELECT 1 FROM {ORDERS} o WHERE o.user_id = u.id
        )
        ORDER BY u.id
    """
    return _run(sql)


def monthly_revenue():
    """CTE + window function: monthly revenue from paid orders, with a
    running cumulative total computed via SUM() OVER."""
    sql = f"""
        WITH monthly AS (
            SELECT
                date_trunc('month', o.created_at) AS month,
                SUM(oi.quantity * oi.price) AS revenue
            FROM {ORDERS} o
            JOIN {ORDER_ITEMS} oi ON oi.order_id = o.id
            WHERE o.payment_status = 'paid'
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
    sql = f"""
        SELECT
            COUNT(*) AS total_orders,
            COUNT(*) FILTER (WHERE status = 'pending') AS pending_count,
            COUNT(*) FILTER (WHERE status = 'confirmed') AS confirmed_count,
            COUNT(*) FILTER (WHERE status = 'shipped') AS shipped_count,
            COUNT(*) FILTER (WHERE status = 'delivered') AS delivered_count,
            COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_count,
            COALESCE(SUM(total_amount) FILTER (WHERE payment_status = 'paid'), 0) AS paid_revenue
        FROM {ORDERS}
    """
    return _run(sql)
