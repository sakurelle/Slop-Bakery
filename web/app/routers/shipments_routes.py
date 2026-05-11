from datetime import date

from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_action, authorize_section, forbidden_response, redirect_to, render_template, set_flash
from ..database import fetch_all, fetch_one, get_db, next_id
from ..permissions import has_action
from ..utils import build_options, clean_text, parse_datetime_local, parse_decimal, parse_int


router = APIRouter()


def shipment_fields(orders, statuses, data=None):
    data = data or {}
    return [
        {"name": "order_id", "label": "Заказ", "type": "select", "required": True, "value": data.get("order_id", ""), "options": build_options(orders, "order_id", "display_name")},
        {"name": "shipped_at", "label": "Дата отгрузки", "type": "datetime-local", "value": data.get("shipped_at", "")},
        {"name": "status_code", "label": "Статус", "type": "select", "required": True, "value": data.get("status_code", "planned"), "options": build_options(statuses, "status_code", "name")},
        {"name": "delivery_address", "label": "Адрес доставки", "type": "textarea", "required": True, "value": data.get("delivery_address", "")},
        {"name": "waybill_number", "label": "Номер накладной", "type": "text", "value": data.get("waybill_number", "")},
        {"name": "note", "label": "Примечание", "type": "textarea", "value": data.get("note", "")},
    ]


def shipment_item_fields(order_items, finished_stock, data=None):
    data = data or {}
    return [
        {"name": "order_item_id", "label": "Позиция заказа", "type": "select", "required": True, "value": data.get("order_item_id", ""), "options": build_options(order_items, "order_item_id", "display_name")},
        {"name": "finished_stock_id", "label": "Партия готовой продукции", "type": "select", "required": True, "value": data.get("finished_stock_id", ""), "options": build_options(finished_stock, "finished_stock_id", "display_name")},
        {"name": "quantity", "label": "Количество", "type": "number", "required": True, "step": "0.001", "min": "0.001", "value": data.get("quantity", "")},
    ]


def fetch_shipment_for_user(shipment_id: int, user: dict):
    query = """
        SELECT
            s.*,
            o.order_number,
            o.customer_id
        FROM shipments AS s
        JOIN customer_orders AS o ON o.order_id = s.order_id
        WHERE s.shipment_id = %s
    """
    params = [shipment_id]
    if "client" in user.get("roles", []):
        query += " AND o.customer_id = %s"
        params.append(user["customer_id"])
    return fetch_one(query, tuple(params))


def fetch_shipment_item_form_data(order_id: int):
    order_items = fetch_all(
        """
        SELECT
            oi.order_item_id,
            p.name || ' / заказано ' || oi.quantity::TEXT AS display_name
        FROM order_items AS oi
        JOIN products AS p ON p.product_id = oi.product_id
        WHERE oi.order_id = %s
        ORDER BY oi.order_item_id
        """,
        (order_id,),
    )
    finished_stock = fetch_all(
        """
        SELECT
            fgs.finished_stock_id,
            p.name || ' / ' || fgs.batch_number || ' / остаток ' || fgs.quantity_current::TEXT AS display_name
        FROM finished_goods_stock AS fgs
        JOIN products AS p ON p.product_id = fgs.product_id
        WHERE fgs.quantity_current > 0
          AND fgs.expiry_date >= CURRENT_DATE
        ORDER BY fgs.expiry_date, fgs.finished_stock_id
        """
    )
    return order_items, finished_stock


@router.get("/shipments")
def shipments_list(request: Request):
    user = authorize_section(request, "shipments")
    if not isinstance(user, dict):
        return user
    query = """
        SELECT
            s.shipment_id,
            s.shipment_number,
            o.order_number,
            s.shipped_at,
            s.status_code,
            s.waybill_number
        FROM shipments AS s
        JOIN customer_orders AS o ON o.order_id = s.order_id
    """
    params = ()
    if "client" in user.get("roles", []):
        query += " WHERE o.customer_id = %s "
        params = (user["customer_id"],)
    query += " ORDER BY s.shipped_at DESC NULLS LAST, s.shipment_id DESC"
    rows = fetch_all(query, params)
    for row in rows:
        row["_detail_url"] = f"/shipments/{row['shipment_id']}"
    context = {
        "title": "Отгрузки",
        "subtitle": "Документы отгрузки и статусы отправки.",
        "headers": [
            ("shipment_id", "ID"),
            ("shipment_number", "Номер отгрузки"),
            ("order_number", "Заказ"),
            ("shipped_at", "Дата отгрузки"),
            ("status_code", "Статус"),
            ("waybill_number", "Накладная"),
        ],
        "rows": rows,
    }
    if has_action(user, "shipments.create"):
        context["create_url"] = "/shipments/new"
        context["create_label"] = "Создать отгрузку"
    return render_template(request, "table_list.html", context)


@router.get("/shipments/new")
def shipment_new_page(request: Request):
    user = authorize_action(request, "shipments.create", "У вас нет прав на создание отгрузок.")
    if not isinstance(user, dict):
        return user
    orders = fetch_all(
        """
        SELECT order_id, order_number || ' / ' || status_code AS display_name
        FROM customer_orders
        WHERE status_code IN ('ready', 'shipped')
        ORDER BY order_id DESC
        """
    )
    statuses = fetch_all("SELECT status_code, name FROM shipment_statuses ORDER BY name")
    return render_template(request, "form.html", {"title": "Создать отгрузку", "action": "/shipments/new", "fields": shipment_fields(orders, statuses), "back_url": "/shipments", "submit_label": "Создать отгрузку"})


@router.post("/shipments/new")
def shipment_new(
    request: Request,
    order_id: str = Form(...),
    shipped_at: str = Form(""),
    status_code: str = Form(...),
    delivery_address: str = Form(...),
    waybill_number: str = Form(""),
    note: str = Form(""),
):
    user = authorize_action(request, "shipments.create", "У вас нет прав на создание отгрузок.")
    if not isinstance(user, dict):
        return user
    orders = fetch_all(
        """
        SELECT order_id, order_number || ' / ' || status_code AS display_name
        FROM customer_orders
        WHERE status_code IN ('ready', 'shipped')
        ORDER BY order_id DESC
        """
    )
    statuses = fetch_all("SELECT status_code, name FROM shipment_statuses ORDER BY name")
    form_data = {"order_id": order_id, "shipped_at": shipped_at, "status_code": status_code, "delivery_address": delivery_address, "waybill_number": waybill_number, "note": note}
    try:
        order_id_value = parse_int(order_id, "Заказ")
        shipped_at_value = parse_datetime_local(shipped_at, "Дата отгрузки", allow_none=True)
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            shipment_id = next_id(conn, "shipments", "shipment_id")
            shipment_number = f"SHP-WEB-{shipment_id:04d}"
            with conn.cursor() as cur:
                cur.execute("SELECT order_date, status_code FROM customer_orders WHERE order_id = %s", (order_id_value,))
                order = cur.fetchone()
                if not order:
                    raise ValueError("Выбранный заказ не существует.")
                if order["status_code"] not in {"ready", "shipped"}:
                    raise ValueError("Создавать отгрузку можно только для заказа, готового к отгрузке.")
                if shipped_at_value and shipped_at_value < order["order_date"]:
                    raise ValueError("Дата отгрузки не может быть раньше даты заказа.")
                cur.execute(
                    """
                    INSERT INTO shipments (
                        shipment_id, shipment_number, order_id, shipped_at, status_code,
                        delivery_address, waybill_number, created_by_user_id, note
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        shipment_id,
                        shipment_number,
                        order_id_value,
                        shipped_at_value,
                        clean_text(status_code),
                        clean_text(delivery_address),
                        clean_text(waybill_number),
                        user["user_id"],
                        clean_text(note),
                    ),
                )
        set_flash(request, "Отгрузка создана. Теперь можно добавить её состав.")
        return redirect_to(f"/shipments/{shipment_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": "Создать отгрузку", "action": "/shipments/new", "fields": shipment_fields(orders, statuses, form_data), "back_url": "/shipments", "submit_label": "Создать отгрузку", "error_message": str(exc)}, status_code=400)


@router.get("/shipments/{shipment_id}")
def shipment_detail(request: Request, shipment_id: int):
    user = authorize_section(request, "shipments")
    if not isinstance(user, dict):
        return user
    shipment = fetch_shipment_for_user(shipment_id, user)
    if not shipment:
        return render_template(request, "error.html", {"title": "Отгрузка не найдена", "message": "Отгрузка не найдена или недоступна."}, status_code=404)
    items = fetch_all(
        """
        SELECT
            si.shipment_item_id,
            p.name AS product_name,
            si.quantity,
            fgs.batch_number
        FROM shipment_items AS si
        JOIN products AS p ON p.product_id = si.product_id
        LEFT JOIN finished_goods_stock AS fgs ON fgs.finished_stock_id = si.finished_stock_id
        WHERE si.shipment_id = %s
        ORDER BY si.shipment_item_id
        """,
        (shipment_id,),
    )
    extra_actions = []
    if has_action(user, "shipments.add_item"):
        extra_actions.append({"label": "Добавить позицию", "url": f"/shipments/{shipment_id}/items/new"})
    if has_action(user, "shipments.change_status"):
        extra_actions.append({"label": "Изменить статус", "url": f"/shipments/{shipment_id}/status"})
    return render_template(
        request,
        "detail.html",
        {
            "title": shipment["shipment_number"],
            "back_url": "/shipments",
            "extra_actions": extra_actions,
            "details": [
                ("ID", shipment["shipment_id"]),
                ("Заказ", shipment["order_number"]),
                ("Дата отгрузки", shipment["shipped_at"]),
                ("Статус", shipment["status_code"]),
                ("Адрес доставки", shipment["delivery_address"]),
                ("Номер накладной", shipment["waybill_number"]),
                ("Примечание", shipment["note"]),
            ],
            "sections": [
                {
                    "title": "Состав отгрузки",
                    "headers": [("shipment_item_id", "ID"), ("product_name", "Продукция"), ("quantity", "Количество"), ("batch_number", "Партия")],
                    "rows": items,
                    "empty_message": "Состав отгрузки ещё не добавлен.",
                }
            ],
        },
    )


@router.get("/shipments/{shipment_id}/items/new")
def shipment_item_new_page(request: Request, shipment_id: int):
    user = authorize_action(request, "shipments.add_item", "У вас нет прав на добавление позиций отгрузки.")
    if not isinstance(user, dict):
        return user
    shipment = fetch_shipment_for_user(shipment_id, user)
    if not shipment:
        return render_template(request, "error.html", {"title": "Отгрузка не найдена", "message": "Карточка отгрузки не найдена."}, status_code=404)
    order_items, finished_stock = fetch_shipment_item_form_data(shipment["order_id"])
    return render_template(request, "form.html", {"title": f"Добавить позицию в отгрузку #{shipment_id}", "action": f"/shipments/{shipment_id}/items/new", "fields": shipment_item_fields(order_items, finished_stock), "back_url": f"/shipments/{shipment_id}", "submit_label": "Добавить позицию"})


@router.post("/shipments/{shipment_id}/items/new")
def shipment_item_new(
    request: Request,
    shipment_id: int,
    order_item_id: str = Form(...),
    finished_stock_id: str = Form(...),
    quantity: str = Form(...),
):
    user = authorize_action(request, "shipments.add_item", "У вас нет прав на добавление позиций отгрузки.")
    if not isinstance(user, dict):
        return user
    shipment = fetch_shipment_for_user(shipment_id, user)
    if not shipment:
        return render_template(request, "error.html", {"title": "Отгрузка не найдена", "message": "Карточка отгрузки не найдена."}, status_code=404)
    order_items, finished_stock = fetch_shipment_item_form_data(shipment["order_id"])
    form_data = {"order_item_id": order_item_id, "finished_stock_id": finished_stock_id, "quantity": quantity}
    try:
        order_item_id_value = parse_int(order_item_id, "Позиция заказа")
        finished_stock_id_value = parse_int(finished_stock_id, "Партия готовой продукции")
        quantity_value = parse_decimal(quantity, "Количество")
        if quantity_value <= 0:
            raise ValueError("Количество должно быть больше нуля.")

        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            shipment_item_id = next_id(conn, "shipment_items", "shipment_item_id")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT order_item_id, order_id, product_id, quantity
                    FROM order_items
                    WHERE order_item_id = %s
                    """,
                    (order_item_id_value,),
                )
                order_item = cur.fetchone()
                if not order_item or order_item["order_id"] != shipment["order_id"]:
                    raise ValueError("Позиция заказа не относится к этой отгрузке.")

                cur.execute(
                    """
                    SELECT finished_stock_id, product_id, quantity_current, expiry_date
                    FROM finished_goods_stock
                    WHERE finished_stock_id = %s
                    """,
                    (finished_stock_id_value,),
                )
                stock = cur.fetchone()
                if not stock:
                    raise ValueError("Выбранная партия готовой продукции не существует.")
                if stock["product_id"] != order_item["product_id"]:
                    raise ValueError("Партия готовой продукции не соответствует продукту в позиции заказа.")
                if stock["expiry_date"] < date.today():
                    raise ValueError("Нельзя отгружать просроченную партию готовой продукции.")
                if stock["quantity_current"] < quantity_value:
                    raise ValueError("На складе недостаточно готовой продукции для отгрузки.")

                cur.execute(
                    """
                    SELECT COALESCE(SUM(quantity), 0) AS shipped_quantity
                    FROM shipment_items
                    WHERE order_item_id = %s
                    """,
                    (order_item_id_value,),
                )
                shipped = cur.fetchone()
                if shipped["shipped_quantity"] + quantity_value > order_item["quantity"]:
                    raise ValueError("Нельзя отгрузить больше, чем заказано в позиции заказа.")

                cur.execute(
                    """
                    INSERT INTO shipment_items (
                        shipment_item_id, shipment_id, order_item_id, product_id, finished_stock_id, quantity
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        shipment_item_id,
                        shipment_id,
                        order_item_id_value,
                        order_item["product_id"],
                        finished_stock_id_value,
                        quantity_value,
                    ),
                )
                cur.execute(
                    """
                    UPDATE finished_goods_stock
                    SET quantity_current = quantity_current - %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE finished_stock_id = %s
                    """,
                    (quantity_value, finished_stock_id_value),
                )
        set_flash(request, "Позиция отгрузки успешно добавлена, остаток готовой продукции уменьшен.")
        return redirect_to(f"/shipments/{shipment_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"Добавить позицию в отгрузку #{shipment_id}", "action": f"/shipments/{shipment_id}/items/new", "fields": shipment_item_fields(order_items, finished_stock, form_data), "back_url": f"/shipments/{shipment_id}", "submit_label": "Добавить позицию", "error_message": str(exc)}, status_code=400)


@router.get("/shipments/{shipment_id}/status")
def shipment_status_page(request: Request, shipment_id: int):
    user = authorize_action(request, "shipments.change_status", "У вас нет прав на изменение статуса отгрузки.")
    if not isinstance(user, dict):
        return user
    shipment = fetch_shipment_for_user(shipment_id, user)
    if not shipment:
        return render_template(request, "error.html", {"title": "Отгрузка не найдена", "message": "Карточка отгрузки не найдена."}, status_code=404)
    statuses = fetch_all("SELECT status_code, name FROM shipment_statuses ORDER BY name")
    return render_template(request, "form.html", {"title": f"Изменить статус отгрузки #{shipment_id}", "action": f"/shipments/{shipment_id}/status", "fields": [{"name": "status_code", "label": "Статус", "type": "select", "required": True, "value": shipment['status_code'], "options": build_options(statuses, 'status_code', 'name')}], "back_url": f"/shipments/{shipment_id}", "submit_label": "Обновить статус"})


@router.post("/shipments/{shipment_id}/status")
def shipment_status_update(request: Request, shipment_id: int, status_code: str = Form(...)):
    user = authorize_action(request, "shipments.change_status", "У вас нет прав на изменение статуса отгрузки.")
    if not isinstance(user, dict):
        return user
    shipment = fetch_shipment_for_user(shipment_id, user)
    if not shipment:
        return render_template(request, "error.html", {"title": "Отгрузка не найдена", "message": "Карточка отгрузки не найдена."}, status_code=404)
    statuses = fetch_all("SELECT status_code, name FROM shipment_statuses ORDER BY name")
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE shipments SET status_code = %s WHERE shipment_id = %s", (clean_text(status_code), shipment_id))
        set_flash(request, "Статус отгрузки успешно обновлён.")
        return redirect_to(f"/shipments/{shipment_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"Изменить статус отгрузки #{shipment_id}", "action": f"/shipments/{shipment_id}/status", "fields": [{"name": "status_code", "label": "Статус", "type": "select", "required": True, "value": status_code, "options": build_options(statuses, 'status_code', 'name')}], "back_url": f"/shipments/{shipment_id}", "submit_label": "Обновить статус", "error_message": str(exc)}, status_code=400)
