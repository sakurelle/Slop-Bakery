from decimal import Decimal

from fastapi import APIRouter, Form, Query, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_action, authorize_section, forbidden_response, redirect_to, render_template, set_flash
from ..database import fetch_all, fetch_one, get_db
from ..permissions import has_action
from ..utils import build_options, clean_text, parse_date, parse_decimal, parse_int


router = APIRouter()

ORDER_STATUS_TRANSITIONS = {
    "draft": {"confirmed", "cancelled"},
    "confirmed": {"in_production", "cancelled"},
    "in_production": {"ready"},
    "ready": {"shipped"},
    "shipped": {"completed"},
    "completed": set(),
    "cancelled": set(),
}


def is_client(user: dict) -> bool:
    return "client" in user.get("roles", [])


def order_fields(customers, data=None, is_client_user: bool = False, customer_id_value=None):
    data = data or {}
    fields = []
    if is_client_user:
        fields.append({"name": "customer_id", "label": "Клиент", "type": "hidden", "value": customer_id_value})
        fields.append({"name": "status_code", "label": "Статус", "type": "hidden", "value": "draft"})
    else:
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
    fields.extend(
        [
            {"name": "planned_shipment_date", "label": "Плановая дата отгрузки", "type": "date", "value": data.get("planned_shipment_date", "")},
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
            "options": build_options(products, "product_id", "display_name"),
        },
        {"name": "quantity", "label": "Количество", "type": "number", "required": True, "step": "0.001", "min": "0.001", "value": data.get("quantity", "")},
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


def get_order_query() -> str:
    return """
        SELECT
            o.*,
            COALESCE(c.company_name, c.full_name) AS customer_name
        FROM customer_orders AS o
        JOIN customers AS c ON c.customer_id = o.customer_id
        WHERE o.order_id = %s
    """


def fetch_order_for_user(order_id: int, user: dict):
    query = get_order_query()
    params = [order_id]
    if is_client(user):
        query += " AND o.customer_id = %s"
        params.append(user["customer_id"])
    return fetch_one(query, tuple(params))


def get_next_statuses_for_user(order: dict, user: dict) -> list[str]:
    current_status = order["status_code"]
    allowed = ORDER_STATUS_TRANSITIONS.get(current_status, set())
    if not allowed:
        return []
    if "admin" in user.get("roles", []):
        return sorted(allowed)
    if "technologist" in user.get("roles", []) and current_status == "confirmed":
        return ["in_production"] if "in_production" in allowed else []
    return []


def validate_order_status_change(order: dict, new_status: str, user: dict) -> None:
    next_statuses = get_next_statuses_for_user(order, user)
    if new_status not in next_statuses:
        raise ValueError("Недопустимый переход статуса заказа для вашей роли.")


def fetch_order_status_options(order: dict, user: dict):
    next_statuses = get_next_statuses_for_user(order, user)
    if not next_statuses:
        return []
    return fetch_all(
        """
        SELECT status_code, name
        FROM order_statuses
        WHERE status_code = ANY(%s)
        ORDER BY name
        """,
        (next_statuses,),
    )


def fetch_products_for_order_items():
    return fetch_all(
        """
        SELECT
            p.product_id,
            p.name,
            p.name || ' / доступно ' || COALESCE(stock.quantity_available, 0)::TEXT AS display_name,
            COALESCE(stock.quantity_available, 0) AS quantity_available
        FROM products AS p
        LEFT JOIN (
            SELECT fgs.product_id, SUM(fgs.quantity_current) AS quantity_available
            FROM finished_goods_stock AS fgs
            WHERE fgs.quantity_current > 0
              AND fgs.expiry_date >= CURRENT_DATE
              AND EXISTS (
                  SELECT 1
                  FROM quality_checks AS qc_passed
                  WHERE qc_passed.production_batch_id = fgs.production_batch_id
                    AND qc_passed.check_type = 'finished_product'
                    AND qc_passed.result_code = 'passed'
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM quality_checks AS qc_failed
                  WHERE qc_failed.production_batch_id = fgs.production_batch_id
                    AND qc_failed.check_type = 'finished_product'
                    AND qc_failed.result_code = 'failed'
              )
            GROUP BY fgs.product_id
        ) AS stock ON stock.product_id = p.product_id
        WHERE p.is_active = TRUE
          AND COALESCE(stock.quantity_available, 0) > 0
        ORDER BY p.name
        """
    )


def get_product_for_order(conn, product_id: int):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                p.product_id,
                p.name,
                p.price,
                COALESCE(stock.quantity_available, 0) AS quantity_available
            FROM products AS p
            LEFT JOIN (
                SELECT fgs.product_id, SUM(fgs.quantity_current) AS quantity_available
                FROM finished_goods_stock AS fgs
                WHERE fgs.quantity_current > 0
                  AND fgs.expiry_date >= CURRENT_DATE
                  AND EXISTS (
                      SELECT 1
                      FROM quality_checks AS qc_passed
                      WHERE qc_passed.production_batch_id = fgs.production_batch_id
                        AND qc_passed.check_type = 'finished_product'
                        AND qc_passed.result_code = 'passed'
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM quality_checks AS qc_failed
                      WHERE qc_failed.production_batch_id = fgs.production_batch_id
                        AND qc_failed.check_type = 'finished_product'
                        AND qc_failed.result_code = 'failed'
                  )
                GROUP BY fgs.product_id
            ) AS stock ON stock.product_id = p.product_id
            WHERE p.product_id = %s
              AND p.is_active = TRUE
            """,
            (product_id,),
        )
        return cur.fetchone()


def ensure_paid_invoice_for_order(conn, order_id: int):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) AS invoice_count,
                COUNT(*) FILTER (WHERE status_code = 'paid') AS paid_count
            FROM invoices
            WHERE order_id = %s
            """,
            (order_id,),
        )
        row = cur.fetchone()
        if not row or row["invoice_count"] == 0:
            raise ValueError("Заказ нельзя отгрузить: счёт ещё не создан.")
        if row["paid_count"] == 0:
            raise ValueError("Заказ нельзя отгрузить: счёт не оплачен.")


def ensure_order_shipment_coverage(conn, order_id: int, shipment_statuses: tuple[str, ...], error_message: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                oi.order_item_id,
                oi.quantity AS ordered_quantity,
                COALESCE(SUM(CASE WHEN s.shipment_id IS NOT NULL THEN si.quantity ELSE 0 END), 0) AS shipped_quantity
            FROM order_items AS oi
            LEFT JOIN shipment_items AS si ON si.order_item_id = oi.order_item_id
            LEFT JOIN shipments AS s
                ON s.shipment_id = si.shipment_id
               AND s.status_code = ANY(%s)
            WHERE oi.order_id = %s
            GROUP BY oi.order_item_id, oi.quantity
            ORDER BY oi.order_item_id
            """,
            (list(shipment_statuses), order_id),
        )
        rows = cur.fetchall()

    if not rows:
        raise ValueError(error_message)

    for row in rows:
        if Decimal(row["shipped_quantity"]) < Decimal(row["ordered_quantity"]):
            raise ValueError(error_message)


def ensure_order_has_delivered_shipment(conn, order_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM shipments AS s
            WHERE s.order_id = %s
              AND s.status_code = 'delivered'
            LIMIT 1
            """,
            (order_id,),
        )
        if not cur.fetchone():
            raise ValueError(
                "Заказ нельзя завершить, пока связанная отгрузка не имеет статус "
                "«Доставлена». Перейдите в раздел «Отгрузки» и обновите статус отгрузки."
            )


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
    if is_client(user):
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

    context = {
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
            "show_filters": not is_client(user),
        },
    }
    if has_action(user, "orders.create"):
        context["create_url"] = "/orders/new"
        context["create_label"] = "Создать заказ"
    return render_template(request, "table_list.html", context)


@router.get("/orders/new")
def order_new_page(request: Request):
    user = authorize_action(request, "orders.create", "У вас нет прав на создание заказов.")
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
    return render_template(
        request,
        "form.html",
        {
            "title": "Создать заказ",
            "action": "/orders/new",
            "fields": order_fields(customers, is_client_user=is_client(user), customer_id_value=user.get("customer_id")),
            "back_url": "/orders",
            "submit_label": "Создать заказ",
        },
    )


@router.post("/orders/new")
def order_new(
    request: Request,
    customer_id: str = Form(""),
    planned_shipment_date: str = Form(""),
    comment: str = Form(""),
):
    user = authorize_action(request, "orders.create", "У вас нет прав на создание заказов.")
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
    is_client_user = is_client(user)
    customer_value = user["customer_id"] if is_client_user else customer_id
    form_data = {"customer_id": customer_value, "planned_shipment_date": planned_shipment_date, "comment": comment}

    if is_client_user and not user.get("customer_id"):
        return forbidden_response(request, "Для клиентского пользователя не привязан клиент. Обратитесь к администратору.")

    try:
        customer_value = user["customer_id"] if is_client_user else parse_int(customer_id, "Клиент")
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH new_order AS (
                        SELECT nextval(pg_get_serial_sequence('customer_orders', 'order_id')) AS order_id
                    )
                    INSERT INTO customer_orders (
                        order_id, order_number, customer_id, planned_shipment_date, status_code, created_by_user_id, comment
                    )
                    SELECT
                        new_order.order_id,
                        'ORD-WEB-' || LPAD(new_order.order_id::TEXT, 4, '0'),
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    FROM new_order
                    RETURNING order_id
                    """,
                    (
                        customer_value,
                        parse_date(planned_shipment_date, "Плановая дата отгрузки", allow_none=True),
                        "draft",
                        user["user_id"],
                        clean_text(comment),
                    ),
                )
                order_id = cur.fetchone()["order_id"]
        set_flash(request, "Заказ создан со статусом «Черновик». Теперь можно добавить его позиции.")
        return redirect_to(f"/orders/{order_id}")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "Не удалось создать заказ. Проверьте корректность данных и попробуйте снова."

    return render_template(
        request,
        "form.html",
        {
            "title": "Создать заказ",
            "action": "/orders/new",
            "fields": order_fields(customers, form_data, is_client_user=is_client_user, customer_id_value=user.get("customer_id")),
            "back_url": "/orders",
            "submit_label": "Создать заказ",
            "error_message": error_message,
        },
        status_code=400,
    )


@router.get("/orders/{order_id}")
def order_detail(request: Request, order_id: int):
    user = authorize_section(request, "orders")
    if not isinstance(user, dict):
        return user

    order = fetch_order_for_user(order_id, user)
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
    shipments = fetch_all(
        """
        SELECT
            shipment_id,
            shipment_number,
            shipped_at,
            status_code,
            delivery_address
        FROM shipments
        WHERE order_id = %s
        ORDER BY shipment_id
        """,
        (order_id,),
    )
    for shipment in shipments:
        shipment["_detail_url"] = f"/shipments/{shipment['shipment_id']}"
        if has_action(user, "shipments.change_status") and shipment["status_code"] in {"planned", "shipped"}:
            shipment["_row_actions"] = [
                {"label": "Изменить статус", "url": f"/shipments/{shipment['shipment_id']}/status"}
            ]

    extra_actions = []
    if has_action(user, "orders.add_item") and order["status_code"] == "draft":
        extra_actions.append({"label": "Добавить позицию", "url": f"/orders/{order_id}/items/new"})
    if has_action(user, "orders.change_status") and get_next_statuses_for_user(order, user):
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
                },
                {
                    "title": "Связанные отгрузки",
                    "headers": [("shipment_number", "Отгрузка"), ("shipped_at", "Дата"), ("status_code", "Статус"), ("delivery_address", "Адрес")],
                    "rows": shipments,
                    "empty_message": "Для заказа ещё нет отгрузок.",
                }
            ],
        },
    )


@router.get("/orders/{order_id}/items/new")
def order_item_new_page(request: Request, order_id: int):
    user = authorize_action(request, "orders.add_item", "У вас нет прав на добавление позиций заказа.")
    if not isinstance(user, dict):
        return user

    order = fetch_order_for_user(order_id, user)
    if not order:
        return render_template(request, "error.html", {"title": "Заказ не найден", "message": "Заказ не найден или недоступен."}, status_code=404)
    if order["status_code"] != "draft":
        return forbidden_response(request, "Добавлять позиции можно только в заказ со статусом «Черновик».")

    products = fetch_products_for_order_items()
    return render_template(
        request,
        "form.html",
        {
            "title": f"Добавить позицию в заказ #{order_id}",
            "action": f"/orders/{order_id}/items/new",
            "fields": order_item_fields(products),
            "back_url": f"/orders/{order_id}",
            "submit_label": "Добавить позицию",
        },
    )


@router.post("/orders/{order_id}/items/new")
def order_item_new(
    request: Request,
    order_id: int,
    product_id: str = Form(...),
    quantity: str = Form(...),
):
    user = authorize_action(request, "orders.add_item", "У вас нет прав на добавление позиций заказа.")
    if not isinstance(user, dict):
        return user

    order = fetch_order_for_user(order_id, user)
    if not order:
        return render_template(request, "error.html", {"title": "Заказ не найден", "message": "Заказ не найден или недоступен."}, status_code=404)
    products = fetch_products_for_order_items()
    form_data = {"product_id": product_id, "quantity": quantity}

    if order["status_code"] != "draft":
        return forbidden_response(request, "Редактировать состав заказа можно только пока он находится в статусе «Черновик».")

    try:
        quantity_value = parse_decimal(quantity, "Количество")
        if quantity_value <= 0:
            raise ValueError("Количество должно быть больше нуля.")
        product_id_value = parse_int(product_id, "Продукция")

        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                product = get_product_for_order(conn, product_id_value)
                if not product:
                    raise ValueError("Выбранная продукция не существует или недоступна.")

                available_qty = Decimal(product["quantity_available"])
                if available_qty <= 0:
                    raise ValueError("Этой продукции сейчас нет в наличии.")
                if quantity_value > available_qty:
                    raise ValueError(f"Недостаточно готовой продукции на складе. Доступно: {product['quantity_available']}.")

                unit_price_value = Decimal(product["price"])

                cur.execute(
                    """
                    SELECT order_item_id, quantity
                    FROM order_items
                    WHERE order_id = %s AND product_id = %s
                    """,
                    (order_id, product_id_value),
                )
                existing_item = cur.fetchone()

                if existing_item:
                    new_quantity = Decimal(existing_item["quantity"]) + quantity_value
                    if new_quantity > available_qty:
                        raise ValueError(f"Недостаточно готовой продукции на складе. Доступно: {product['quantity_available']}.")
                    cur.execute(
                        """
                        UPDATE order_items
                        SET quantity = %s,
                            unit_price = %s,
                            line_amount = %s
                        WHERE order_item_id = %s
                        """,
                        (
                            new_quantity,
                            unit_price_value,
                            new_quantity * unit_price_value,
                            existing_item["order_item_id"],
                        ),
                    )
                    flash_message = "Позиция уже была в заказе, количество обновлено."
                else:
                    cur.execute(
                        """
                        INSERT INTO order_items (
                            order_id, product_id, quantity, unit_price, line_amount
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            order_id,
                            product_id_value,
                            quantity_value,
                            unit_price_value,
                            quantity_value * unit_price_value,
                        ),
                    )
                    flash_message = "Позиция заказа успешно добавлена. Цена и сумма рассчитаны на сервере."
        set_flash(request, flash_message)
        return redirect_to(f"/orders/{order_id}")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "Не удалось сохранить позицию заказа. Проверьте данные и попробуйте снова."

    return render_template(
        request,
        "form.html",
        {
            "title": f"Добавить позицию в заказ #{order_id}",
            "action": f"/orders/{order_id}/items/new",
            "fields": order_item_fields(products, form_data),
            "back_url": f"/orders/{order_id}",
            "submit_label": "Добавить позицию",
            "error_message": error_message,
        },
        status_code=400,
    )


@router.get("/orders/{order_id}/status")
def order_status_page(request: Request, order_id: int):
    user = authorize_action(request, "orders.change_status", "У вас нет прав на изменение статуса заказа.")
    if not isinstance(user, dict):
        return user

    order = fetch_order_for_user(order_id, user)
    if not order:
        return render_template(request, "error.html", {"title": "Заказ не найден", "message": "Карточка заказа не найдена."}, status_code=404)

    statuses = fetch_order_status_options(order, user)
    if not statuses:
        return forbidden_response(request, "Для текущего статуса заказа у вашей роли нет допустимых переходов.")

    return render_template(
        request,
        "form.html",
        {
            "title": f"Изменить статус заказа #{order_id}",
            "action": f"/orders/{order_id}/status",
            "fields": status_fields(statuses, statuses[0]["status_code"]),
            "back_url": f"/orders/{order_id}",
            "submit_label": "Обновить статус",
        },
    )


@router.post("/orders/{order_id}/status")
def order_status_update(request: Request, order_id: int, status_code: str = Form(...)):
    user = authorize_action(request, "orders.change_status", "У вас нет прав на изменение статуса заказа.")
    if not isinstance(user, dict):
        return user

    order = fetch_order_for_user(order_id, user)
    if not order:
        return render_template(request, "error.html", {"title": "Заказ не найден", "message": "Карточка заказа не найдена."}, status_code=404)

    statuses = fetch_order_status_options(order, user)
    try:
        new_status = clean_text(status_code)
        if not new_status:
            raise ValueError("Не выбран новый статус заказа.")
        validate_order_status_change(order, new_status, user)
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            if new_status == "shipped":
                ensure_paid_invoice_for_order(conn, order_id)
                ensure_order_shipment_coverage(conn, order_id, ("shipped", "delivered"), "Заказ нельзя отгрузить: отгрузка не покрывает все позиции заказа.")
            elif new_status == "completed":
                ensure_order_has_delivered_shipment(conn, order_id)

            with conn.cursor() as cur:
                cur.execute("UPDATE customer_orders SET status_code = %s WHERE order_id = %s", (new_status, order_id))
        set_flash(request, "Статус заказа успешно обновлён.")
        return redirect_to(f"/orders/{order_id}")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "Не удалось изменить статус заказа."

    fallback_status = clean_text(status_code) or order["status_code"]
    return render_template(
        request,
        "form.html",
        {
            "title": f"Изменить статус заказа #{order_id}",
            "action": f"/orders/{order_id}/status",
            "fields": status_fields(statuses, fallback_status),
            "back_url": f"/orders/{order_id}",
            "submit_label": "Обновить статус",
            "error_message": error_message,
        },
        status_code=400,
    )
