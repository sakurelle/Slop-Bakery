from fastapi import APIRouter, Form, Query, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_section, redirect_to, render_template, set_flash
from ..database import fetch_all, fetch_one, get_db, next_id
from ..utils import build_options, clean_text, parse_date, parse_decimal, parse_int


router = APIRouter()


def order_fields(customers, statuses, data=None, is_client: bool = False, customer_id_value=None):
    data = data or {}
    fields = []
    if not is_client:
        fields.append(
            {
                "name": "customer_id",
                "label": "Клиент",
                "type": "select",
                "required": True,
                "value": data.get("customer_id", ""),
                "options": build_options(customers, "customer_id", "display_name"),
            }
        )
    else:
        fields.append(
            {
                "name": "customer_id",
                "label": "Клиент",
                "type": "hidden",
                "value": customer_id_value,
            }
        )

    fields.extend(
        [
            {"name": "planned_shipment_date", "label": "Плановая дата отгрузки", "type": "date", "value": data.get("planned_shipment_date", "")},
            {
                "name": "status_code",
                "label": "Статус",
                "type": "select",
                "required": True,
                "value": data.get("status_code", "draft"),
                "options": build_options(statuses, "status_code", "name"),
            },
            {"name": "comment", "label": "Комментарий", "type": "textarea", "value": data.get("comment", "")},
        ]
    )
    return fields


def order_item_fields(products, data=None):
    data = data or {}
    return [
        {
            "name": "product_id",
            "label": "Продукция",
            "type": "select",
            "required": True,
            "value": data.get("product_id", ""),
            "options": build_options(products, "product_id", "name"),
        },
        {"name": "quantity", "label": "Количество", "type": "number", "required": True, "step": "0.001", "min": "0.001", "value": data.get("quantity", "")},
        {"name": "unit_price", "label": "Цена за единицу", "type": "number", "required": True, "step": "0.01", "min": "0", "value": data.get("unit_price", "")},
    ]


def status_fields(statuses, current_status):
    return [
        {
            "name": "status_code",
            "label": "Статус",
            "type": "select",
            "required": True,
            "value": current_status,
            "options": build_options(statuses, "status_code", "name"),
        }
    ]


@router.get("/orders")
def orders_list(
    request: Request,
    customer_id: int | None = Query(default=None),
    status_code: str | None = Query(default=None),
):
    user = authorize_section(request, "orders")
    if not isinstance(user, dict):
        return user

    filters = []
    params = []
    if "client" in user.get("roles", []):
        filters.append("o.customer_id = %s")
        params.append(user["customer_id"])
    elif customer_id:
        filters.append("o.customer_id = %s")
        params.append(customer_id)
    if status_code:
        filters.append("o.status_code = %s")
        params.append(status_code)

    query = """
        SELECT
            o.order_id,
            o.order_number,
            COALESCE(c.company_name, c.full_name) AS customer_name,
            o.order_date,
            o.planned_shipment_date,
            o.status_code
        FROM customer_orders AS o
        JOIN customers AS c ON c.customer_id = o.customer_id
    """
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY o.order_date DESC, o.order_id DESC"

    rows = fetch_all(query, tuple(params))
    for row in rows:
        row["_detail_url"] = f"/orders/{row['order_id']}"

    customers = fetch_all(
        """
        SELECT customer_id, COALESCE(company_name, full_name) AS display_name
        FROM customers
        ORDER BY display_name
        """
    )
    statuses = fetch_all("SELECT status_code, name FROM order_statuses ORDER BY name")

    return render_template(
        request,
        "table_list.html",
        {
            "title": "Заказы",
            "subtitle": "Заказы клиентов с фильтрацией по клиенту и статусу.",
            "headers": [
                ("order_id", "ID"),
                ("order_number", "Номер заказа"),
                ("customer_name", "Клиент"),
                ("order_date", "Дата заказа"),
                ("planned_shipment_date", "Плановая отгрузка"),
                ("status_code", "Статус"),
            ],
            "rows": rows,
            "create_url": "/orders/new",
            "create_label": "Создать заказ",
            "filters": {
                "action": "/orders",
                "fields": [
                    {
                        "name": "customer_id",
                        "label": "Клиент",
                        "type": "select",
                        "value": customer_id or "",
                        "options": build_options(customers, "customer_id", "display_name", blank_label="Все клиенты"),
                    },
                    {
                        "name": "status_code",
                        "label": "Статус",
                        "type": "select",
                        "value": status_code or "",
                        "options": build_options(statuses, "status_code", "name", blank_label="Все статусы"),
                    },
                ],
                "show_filters": "client" not in user.get("roles", []),
            },
        },
    )


@router.get("/orders/new")
def order_new_page(request: Request):
    user = authorize_section(request, "orders")
    if not isinstance(user, dict):
        return user
    customers = fetch_all(
        """
        SELECT customer_id, COALESCE(company_name, full_name) AS display_name
        FROM customers
        WHERE is_active = TRUE
        ORDER BY display_name
        """
    )
    statuses = fetch_all("SELECT status_code, name FROM order_statuses ORDER BY name")
    is_client = "client" in user.get("roles", [])
    return render_template(
        request,
        "form.html",
        {
            "title": "Создать заказ",
            "action": "/orders/new",
            "fields": order_fields(customers, statuses, is_client=is_client, customer_id_value=user.get("customer_id")),
            "back_url": "/orders",
            "submit_label": "Создать заказ",
        },
    )


@router.post("/orders/new")
def order_new(
    request: Request,
    customer_id: str = Form(""),
    planned_shipment_date: str = Form(""),
    status_code: str = Form(...),
    comment: str = Form(""),
):
    user = authorize_section(request, "orders")
    if not isinstance(user, dict):
        return user

    customers = fetch_all(
        """
        SELECT customer_id, COALESCE(company_name, full_name) AS display_name
        FROM customers
        WHERE is_active = TRUE
        ORDER BY display_name
        """
    )
    statuses = fetch_all("SELECT status_code, name FROM order_statuses ORDER BY name")
    is_client = "client" in user.get("roles", [])
    customer_value = user["customer_id"] if is_client else parse_int(customer_id, "Клиент")
    form_data = {"customer_id": customer_value, "planned_shipment_date": planned_shipment_date, "status_code": status_code, "comment": comment}

    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            order_id = next_id(conn, "customer_orders", "order_id")
            order_number = f"ORD-WEB-{order_id:04d}"
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO customer_orders (
                        order_id, order_number, customer_id, planned_shipment_date, status_code, created_by_user_id, comment
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        order_id,
                        order_number,
                        customer_value,
                        parse_date(planned_shipment_date, "Плановая дата отгрузки", allow_none=True),
                        clean_text(status_code),
                        user["user_id"],
                        clean_text(comment),
                    ),
                )
        set_flash(request, "Заказ создан. Теперь можно добавить его позиции.")
        return redirect_to(f"/orders/{order_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(
            request,
            "form.html",
            {
                "title": "Создать заказ",
                "action": "/orders/new",
                "fields": order_fields(customers, statuses, form_data, is_client=is_client, customer_id_value=user.get("customer_id")),
                "back_url": "/orders",
                "submit_label": "Создать заказ",
                "error_message": str(exc),
            },
            status_code=400,
        )


@router.get("/orders/{order_id}")
def order_detail(request: Request, order_id: int):
    user = authorize_section(request, "orders")
    if not isinstance(user, dict):
        return user

    query = """
        SELECT
            o.*,
            COALESCE(c.company_name, c.full_name) AS customer_name
        FROM customer_orders AS o
        JOIN customers AS c ON c.customer_id = o.customer_id
        WHERE o.order_id = %s
    """
    params = [order_id]
    if "client" in user.get("roles", []):
        query += " AND o.customer_id = %s"
        params.append(user["customer_id"])
    order = fetch_one(query, tuple(params))
    if not order:
        return render_template(request, "error.html", {"title": "Заказ не найден", "message": "Заказ не найден или недоступен."}, status_code=404)

    items = fetch_all(
        """
        SELECT oi.order_item_id, p.name AS product_name, oi.quantity, oi.unit_price, oi.line_amount
        FROM order_items AS oi
        JOIN products AS p ON p.product_id = oi.product_id
        WHERE oi.order_id = %s
        ORDER BY oi.order_item_id
        """,
        (order_id,),
    )

    extra_actions = [{"label": "Добавить позицию", "url": f"/orders/{order_id}/items/new"}]
    if "client" not in user.get("roles", []):
        extra_actions.append({"label": "Изменить статус", "url": f"/orders/{order_id}/status"})

    return render_template(
        request,
        "detail.html",
        {
            "title": order["order_number"],
            "back_url": "/orders",
            "extra_actions": extra_actions,
            "details": [
                ("ID", order["order_id"]),
                ("Клиент", order["customer_name"]),
                ("Дата заказа", order["order_date"]),
                ("Плановая дата отгрузки", order["planned_shipment_date"]),
                ("Статус", order["status_code"]),
                ("Комментарий", order["comment"]),
            ],
            "sections": [
                {
                    "title": "Позиции заказа",
                    "headers": [("order_item_id", "ID"), ("product_name", "Продукция"), ("quantity", "Количество"), ("unit_price", "Цена за ед."), ("line_amount", "Сумма")],
                    "rows": items,
                    "empty_message": "Позиции заказа ещё не добавлены.",
                }
            ],
        },
    )


@router.get("/orders/{order_id}/items/new")
def order_item_new_page(request: Request, order_id: int):
    user = authorize_section(request, "orders")
    if not isinstance(user, dict):
        return user
    products = fetch_all("SELECT product_id, name FROM products WHERE is_active = TRUE ORDER BY name")
    return render_template(request, "form.html", {"title": f"Добавить позицию в заказ #{order_id}", "action": f"/orders/{order_id}/items/new", "fields": order_item_fields(products), "back_url": f"/orders/{order_id}", "submit_label": "Добавить позицию"})


@router.post("/orders/{order_id}/items/new")
def order_item_new(
    request: Request,
    order_id: int,
    product_id: str = Form(...),
    quantity: str = Form(...),
    unit_price: str = Form(...),
):
    user = authorize_section(request, "orders")
    if not isinstance(user, dict):
        return user
    products = fetch_all("SELECT product_id, name FROM products WHERE is_active = TRUE ORDER BY name")
    form_data = {"product_id": product_id, "quantity": quantity, "unit_price": unit_price}
    try:
        quantity_value = parse_decimal(quantity, "Количество")
        unit_price_value = parse_decimal(unit_price, "Цена за единицу")
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            order_item_id = next_id(conn, "order_items", "order_item_id")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO order_items (
                        order_item_id, order_id, product_id, quantity, unit_price, line_amount
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        order_item_id,
                        order_id,
                        parse_int(product_id, "Продукция"),
                        quantity_value,
                        unit_price_value,
                        quantity_value * unit_price_value,
                    ),
                )
        set_flash(request, "Позиция заказа успешно добавлена.")
        return redirect_to(f"/orders/{order_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"Добавить позицию в заказ #{order_id}", "action": f"/orders/{order_id}/items/new", "fields": order_item_fields(products, form_data), "back_url": f"/orders/{order_id}", "submit_label": "Добавить позицию", "error_message": str(exc)}, status_code=400)


@router.get("/orders/{order_id}/status")
def order_status_page(request: Request, order_id: int):
    user = authorize_section(request, "orders")
    if not isinstance(user, dict):
        return user
    if "client" in user.get("roles", []):
        return render_template(request, "error.html", {"title": "Доступ запрещён", "message": "Клиенты не могут менять статусы заказов."}, status_code=403)
    order = fetch_one("SELECT order_id, status_code FROM customer_orders WHERE order_id = %s", (order_id,))
    if not order:
        return render_template(request, "error.html", {"title": "Заказ не найден", "message": "Карточка заказа не найдена."}, status_code=404)
    statuses = fetch_all("SELECT status_code, name FROM order_statuses ORDER BY name")
    return render_template(request, "form.html", {"title": f"Изменить статус заказа #{order_id}", "action": f"/orders/{order_id}/status", "fields": status_fields(statuses, order['status_code']), "back_url": f"/orders/{order_id}", "submit_label": "Обновить статус"})


@router.post("/orders/{order_id}/status")
def order_status_update(request: Request, order_id: int, status_code: str = Form(...)):
    user = authorize_section(request, "orders")
    if not isinstance(user, dict):
        return user
    if "client" in user.get("roles", []):
        return render_template(request, "error.html", {"title": "Доступ запрещён", "message": "Клиенты не могут менять статусы заказов."}, status_code=403)
    statuses = fetch_all("SELECT status_code, name FROM order_statuses ORDER BY name")
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE customer_orders SET status_code = %s WHERE order_id = %s", (clean_text(status_code), order_id))
        set_flash(request, "Статус заказа успешно обновлён.")
        return redirect_to(f"/orders/{order_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"Изменить статус заказа #{order_id}", "action": f"/orders/{order_id}/status", "fields": status_fields(statuses, status_code), "back_url": f"/orders/{order_id}", "submit_label": "Обновить статус", "error_message": str(exc)}, status_code=400)
