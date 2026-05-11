from fastapi import APIRouter, Request

from ..auth import authorize_action, authorize_section, render_template
from ..database import fetch_all, fetch_one
from ..permissions import get_primary_role, has_action


router = APIRouter()


@router.get("/")
def dashboard(request: Request):
    user = authorize_section(request, "dashboard")
    if not isinstance(user, dict):
        return user

    primary_role = get_primary_role(user)

    if primary_role == "client":
        stats = fetch_one(
            """
            SELECT
                (SELECT COUNT(*) FROM customer_orders WHERE customer_id = %s) AS order_count,
                (SELECT COUNT(*) FROM invoices AS i JOIN customer_orders AS o ON o.order_id = i.order_id WHERE o.customer_id = %s) AS invoice_count,
                (SELECT COUNT(*) FROM shipments AS s JOIN customer_orders AS o ON o.order_id = s.order_id WHERE o.customer_id = %s) AS shipment_count,
                (SELECT COUNT(*) FROM products WHERE is_active = TRUE) AS product_count
            """,
            (user["customer_id"], user["customer_id"], user["customer_id"]),
        )
        recent_orders = fetch_all(
            """
            SELECT
                o.order_id,
                o.order_number,
                o.status_code,
                o.order_date,
                COALESCE(c.company_name, c.full_name) AS customer_name
            FROM customer_orders AS o
            JOIN customers AS c ON c.customer_id = o.customer_id
            WHERE o.customer_id = %s
            ORDER BY o.order_date DESC
            LIMIT 5
            """,
            (user["customer_id"],),
        )
        recent_invoices = fetch_all(
            """
            SELECT i.invoice_number, i.issue_date, i.amount, i.status_code
            FROM invoices AS i
            JOIN customer_orders AS o ON o.order_id = i.order_id
            WHERE o.customer_id = %s
            ORDER BY i.issue_date DESC, i.invoice_id DESC
            LIMIT 5
            """,
            (user["customer_id"],),
        )
        recent_shipments = fetch_all(
            """
            SELECT s.shipment_number, s.shipped_at, s.status_code, s.delivery_address
            FROM shipments AS s
            JOIN customer_orders AS o ON o.order_id = s.order_id
            WHERE o.customer_id = %s
            ORDER BY s.shipped_at DESC NULLS LAST, s.shipment_id DESC
            LIMIT 5
            """,
            (user["customer_id"],),
        )
        available_products = fetch_all(
            """
            SELECT
                p.name,
                p.price,
                p.unit,
                COALESCE(SUM(fgs.quantity_current), 0) AS quantity_available
            FROM products AS p
            LEFT JOIN finished_goods_stock AS fgs
                ON fgs.product_id = p.product_id
               AND fgs.quantity_current > 0
               AND fgs.expiry_date >= CURRENT_DATE
            WHERE p.is_active = TRUE
            GROUP BY p.product_id, p.name, p.price, p.unit
            ORDER BY p.name
            LIMIT 10
            """
        )
        return render_template(
            request,
            "dashboard.html",
            {
                "title": "Личный кабинет",
                "is_client_dashboard": True,
                "stats": stats,
                "recent_orders": recent_orders,
                "recent_invoices": recent_invoices,
                "recent_shipments": recent_shipments,
                "available_products": available_products,
                "recent_audit": [],
                "admin_users": [],
                "roles": [],
            },
        )

    counts = fetch_one(
        """
        SELECT
            (SELECT COUNT(*) FROM customers) AS customer_count,
            (SELECT COUNT(*) FROM customer_orders) AS order_count,
            (SELECT COUNT(*) FROM products) AS product_count,
            (SELECT COUNT(*) FROM raw_materials) AS material_count,
            (
                SELECT COUNT(*)
                FROM customer_orders
                WHERE status_code IN ('confirmed', 'in_production', 'ready', 'shipped')
            ) AS active_order_count,
            (
                SELECT COUNT(*)
                FROM (
                    SELECT rm.material_id
                    FROM raw_materials AS rm
                    LEFT JOIN raw_material_stock AS rms ON rms.material_id = rm.material_id
                    GROUP BY rm.material_id, rm.min_stock_qty
                    HAVING COALESCE(SUM(rms.quantity_current), 0) < rm.min_stock_qty
                ) AS low_stock
            ) AS low_stock_material_count
        """
    )

    recent_orders = fetch_all(
        """
        SELECT
            o.order_id,
            o.order_number,
            o.status_code,
            o.order_date,
            COALESCE(c.company_name, c.full_name) AS customer_name
        FROM customer_orders AS o
        JOIN customers AS c ON c.customer_id = o.customer_id
        ORDER BY o.order_date DESC
        LIMIT 5
        """
    )

    recent_audit = []
    if has_action(user, "audit.view"):
        recent_audit = fetch_all(
            """
            SELECT
                al.changed_at,
                al.action_type,
                al.table_name,
                al.record_id,
                COALESCE(u.username, 'system') AS username
            FROM audit_log AS al
            LEFT JOIN users AS u ON u.user_id = al.user_id
            ORDER BY al.changed_at DESC, al.audit_id DESC
            LIMIT 5
            """
        )

    admin_users = []
    roles = []
    if primary_role == "admin":
        admin_users = fetch_all(
            """
            SELECT
                u.user_id,
                u.username,
                u.full_name,
                u.status_code,
                COALESCE(string_agg(r.role_name, ', ' ORDER BY r.role_name), '') AS roles
            FROM users AS u
            LEFT JOIN user_roles AS ur ON ur.user_id = u.user_id
            LEFT JOIN roles AS r ON r.role_id = ur.role_id
            GROUP BY u.user_id, u.username, u.full_name, u.status_code
            ORDER BY u.user_id
            """
        )
        roles = fetch_all(
            """
            SELECT
                r.role_id,
                r.role_code,
                r.role_name,
                COUNT(ur.user_id) AS assigned_users
            FROM roles AS r
            LEFT JOIN user_roles AS ur ON ur.role_id = r.role_id
            GROUP BY r.role_id, r.role_code, r.role_name
            ORDER BY r.role_id
            """
        )

    return render_template(
        request,
        "dashboard.html",
        {
            "title": "Главная",
            "is_client_dashboard": False,
            "stats": counts,
            "recent_orders": recent_orders,
            "recent_audit": recent_audit,
            "admin_users": admin_users,
            "roles": roles,
        },
    )


@router.get("/admin/users")
def users_list(request: Request):
    user = authorize_action(request, "users.manage", "У вас нет прав на просмотр списка пользователей.")
    if not isinstance(user, dict):
        return user

    rows = fetch_all(
        """
        SELECT
            u.user_id,
            u.username,
            u.full_name,
            u.status_code,
            COALESCE(string_agg(r.role_name, ', ' ORDER BY r.role_name), '') AS roles
        FROM users AS u
        LEFT JOIN user_roles AS ur ON ur.user_id = u.user_id
        LEFT JOIN roles AS r ON r.role_id = ur.role_id
        GROUP BY u.user_id, u.username, u.full_name, u.status_code
        ORDER BY u.user_id
        """
    )
    return render_template(
        request,
        "table_list.html",
        {
            "title": "Пользователи",
            "subtitle": "Административный список пользователей системы.",
            "headers": [
                ("user_id", "ID"),
                ("username", "Логин"),
                ("full_name", "ФИО"),
                ("status_code", "Статус"),
                ("roles", "Роли"),
            ],
            "rows": rows,
        },
    )


@router.get("/admin/roles")
def roles_list(request: Request):
    user = authorize_action(request, "users.manage", "У вас нет прав на просмотр ролей.")
    if not isinstance(user, dict):
        return user

    rows = fetch_all(
        """
        SELECT
            r.role_id,
            r.role_code,
            r.role_name,
            r.description,
            COUNT(ur.user_id) AS assigned_users
        FROM roles AS r
        LEFT JOIN user_roles AS ur ON ur.role_id = r.role_id
        GROUP BY r.role_id, r.role_code, r.role_name, r.description
        ORDER BY r.role_id
        """
    )
    return render_template(
        request,
        "table_list.html",
        {
            "title": "Роли",
            "subtitle": "Административный список логических ролей.",
            "headers": [
                ("role_id", "ID"),
                ("role_code", "Код"),
                ("role_name", "Название"),
                ("description", "Описание"),
                ("assigned_users", "Пользователи"),
            ],
            "rows": rows,
        },
    )
