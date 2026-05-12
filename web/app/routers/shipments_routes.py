from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_action, authorize_section, forbidden_response, redirect_to, render_template, set_flash
from ..database import fetch_all, fetch_one, get_db
from ..permissions import has_action
from ..utils import build_options, clean_text, parse_datetime_local, parse_decimal, parse_int


router = APIRouter()

SHIPMENT_STATUS_TRANSITIONS = {
    "planned": {"shipped", "cancelled"},
    "shipped": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}


def shipment_fields(orders, data=None):
    data = data or {}
    return [
        {"name": "order_id", "label": "Заказ", "type": "select", "required": True, "value": data.get("order_id", ""), "options": build_options(orders, "order_id", "display_name")},
        {"name": "shipped_at", "label": "Дата отгрузки", "type": "datetime-local", "value": data.get("shipped_at", "")},
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


def shipment_status_fields(statuses, current_status):
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


def fetch_shipment_for_user(shipment_id: int, user: dict):
    query = """
        SELECT
            s.*,
            o.order_number,
            o.customer_id,
            o.status_code AS order_status_code
        FROM shipments AS s
        JOIN customer_orders AS o ON o.order_id = s.order_id
        WHERE s.shipment_id = %s
    """
    params = [shipment_id]
    if "client" in user.get("roles", []):
        query += " AND o.customer_id = %s"
        params.append(user["customer_id"])
    return fetch_one(query, tuple(params))


def ensure_order_paid_for_shipping(conn, order_id: int):
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


def ensure_shipment_has_items(conn, shipment_id: int):
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM shipment_items WHERE shipment_id = %s LIMIT 1", (shipment_id,))
        if not cur.fetchone():
            raise ValueError("Нельзя отгрузить пустую отгрузку.")


def get_shippable_orders():
    return fetch_all(
        """
        SELECT o.order_id, o.order_number || ' / ' || o.status_code AS display_name
        FROM customer_orders AS o
        WHERE o.status_code = 'ready'
          AND EXISTS (
              SELECT 1
              FROM invoices AS i
              WHERE i.order_id = o.order_id
                AND i.status_code = 'paid'
          )
        ORDER BY o.order_id DESC
        """
    )


def fetch_shipment_item_form_data(order_id: int):
    order_items = fetch_all(
        """
        SELECT
            oi.order_item_id,
            oi.product_id,
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
            fgs.product_id,
            p.name || ' / ' || fgs.batch_number || ' / остаток ' || fgs.quantity_current::TEXT || ' / годен до ' || fgs.expiry_date::TEXT AS display_name
        FROM finished_goods_stock AS fgs
        JOIN products AS p ON p.product_id = fgs.product_id
        WHERE fgs.quantity_current > 0
          AND fgs.expiry_date >= CURRENT_DATE
          AND fgs.product_id IN (
              SELECT product_id
              FROM order_items
              WHERE order_id = %s
          )
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
        ORDER BY fgs.expiry_date, fgs.finished_stock_id
        """,
        (order_id,),
    )
    return order_items, finished_stock


def get_next_shipment_statuses(shipment: dict) -> list[str]:
    return sorted(SHIPMENT_STATUS_TRANSITIONS.get(shipment["status_code"], set()))


def fetch_shipment_status_options(shipment: dict):
    next_statuses = get_next_shipment_statuses(shipment)
    if not next_statuses:
        return []
    return fetch_all(
        """
        SELECT status_code, name
        FROM shipment_statuses
        WHERE status_code = ANY(%s)
        ORDER BY name
        """,
        (next_statuses,),
    )


def validate_shipment_status_change(shipment: dict, new_status: str):
    if new_status not in SHIPMENT_STATUS_TRANSITIONS.get(shipment["status_code"], set()):
        raise ValueError("Недопустимый переход статуса отгрузки.")


def validate_finished_batch_quality(cur, production_batch_id: int):
    cur.execute(
        """
        SELECT 1
        FROM quality_checks
        WHERE production_batch_id = %s
          AND check_type = 'finished_product'
          AND result_code = 'failed'
        LIMIT 1
        """,
        (production_batch_id,),
    )
    if cur.fetchone():
        raise ValueError("Партия не прошла проверку качества.")

    cur.execute(
        """
        SELECT 1
        FROM quality_checks
        WHERE production_batch_id = %s
          AND check_type = 'finished_product'
          AND result_code = 'passed'
        LIMIT 1
        """,
        (production_batch_id,),
    )
    if not cur.fetchone():
        raise ValueError("Партия готовой продукции не может быть отгружена: нет успешной проверки качества.")


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
    return render_template(
        request,
        "form.html",
        {
            "title": "Создать отгрузку",
            "action": "/shipments/new",
            "fields": shipment_fields(get_shippable_orders()),
            "back_url": "/shipments",
            "submit_label": "Создать отгрузку",
        },
    )


@router.post("/shipments/new")
def shipment_new(
    request: Request,
    order_id: str = Form(...),
    shipped_at: str = Form(""),
    delivery_address: str = Form(...),
    waybill_number: str = Form(""),
    note: str = Form(""),
):
    user = authorize_action(request, "shipments.create", "У вас нет прав на создание отгрузок.")
    if not isinstance(user, dict):
        return user
    orders = get_shippable_orders()
    form_data = {"order_id": order_id, "shipped_at": shipped_at, "delivery_address": delivery_address, "waybill_number": waybill_number, "note": note}
    try:
        order_id_value = parse_int(order_id, "Заказ")
        shipped_at_value = parse_datetime_local(shipped_at, "Дата отгрузки", allow_none=True)
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT order_date, status_code
                    FROM customer_orders
                    WHERE order_id = %s
                    """,
                    (order_id_value,),
                )
                order = cur.fetchone()
                if not order:
                    raise ValueError("Выбранный заказ не существует.")
                if order["status_code"] != "ready":
                    raise ValueError("Создавать отгрузку можно только для заказа со статусом «Готов».")
                ensure_order_paid_for_shipping(conn, order_id_value)
                order_date_value = order.get("order_date")
                if shipped_at_value and order_date_value and shipped_at_value.date() < order_date_value.date():
                    raise ValueError("Дата отгрузки не может быть раньше даты заказа.")
                cur.execute(
                    """
                    WITH new_shipment AS (
                        SELECT nextval(pg_get_serial_sequence('shipments', 'shipment_id')) AS shipment_id
                    )
                    INSERT INTO shipments (
                        shipment_id, shipment_number, order_id, shipped_at, status_code,
                        delivery_address, waybill_number, created_by_user_id, note
                    )
                    SELECT
                        new_shipment.shipment_id,
                        'SHP-WEB-' || LPAD(new_shipment.shipment_id::TEXT, 4, '0'),
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    FROM new_shipment
                    RETURNING shipment_id
                    """,
                    (
                        order_id_value,
                        shipped_at_value,
                        "planned",
                        clean_text(delivery_address),
                        clean_text(waybill_number),
                        user["user_id"],
                        clean_text(note),
                    ),
                )
                shipment_id = cur.fetchone()["shipment_id"]
        set_flash(request, "Отгрузка создана со статусом «Запланирована». Теперь можно добавить её состав.")
        return redirect_to(f"/shipments/{shipment_id}")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "Не удалось создать отгрузку."

    return render_template(
        request,
        "form.html",
        {
            "title": "Создать отгрузку",
            "action": "/shipments/new",
            "fields": shipment_fields(orders, form_data),
            "back_url": "/shipments",
            "submit_label": "Создать отгрузку",
            "error_message": error_message,
        },
        status_code=400,
    )


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
            fgs.batch_number,
            p.unit,
            fgs.expiry_date
        FROM shipment_items AS si
        JOIN products AS p ON p.product_id = si.product_id
        LEFT JOIN finished_goods_stock AS fgs ON fgs.finished_stock_id = si.finished_stock_id
        WHERE si.shipment_id = %s
        ORDER BY si.shipment_item_id
        """,
        (shipment_id,),
    )
    extra_actions = []
    if has_action(user, "shipments.add_item") and shipment["status_code"] == "planned":
        extra_actions.append({"label": "Добавить позицию", "url": f"/shipments/{shipment_id}/items/new"})
    if has_action(user, "shipments.change_status") and get_next_shipment_statuses(shipment):
        extra_actions.append({"label": "Изменить статус", "url": f"/shipments/{shipment_id}/status"})
    if has_action(user, "shipments.report"):
        extra_actions.append({"label": "Отчёт по отгрузке", "url": f"/shipments/{shipment_id}/report"})
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
                    "headers": [("shipment_item_id", "ID"), ("product_name", "Продукция"), ("quantity", "Количество"), ("unit", "Ед."), ("batch_number", "Партия"), ("expiry_date", "Годен до")],
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
    if shipment["status_code"] != "planned":
        return forbidden_response(request, "Добавлять позиции можно только в запланированную отгрузку.")
    order_items, finished_stock = fetch_shipment_item_form_data(shipment["order_id"])
    return render_template(
        request,
        "form.html",
        {
            "title": f"Добавить позицию в отгрузку #{shipment_id}",
            "action": f"/shipments/{shipment_id}/items/new",
            "fields": shipment_item_fields(order_items, finished_stock),
            "back_url": f"/shipments/{shipment_id}",
            "submit_label": "Добавить позицию",
        },
    )


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
    if shipment["status_code"] != "planned":
        return forbidden_response(request, "Добавлять позиции можно только в запланированную отгрузку.")
    try:
        order_item_id_value = parse_int(order_item_id, "Позиция заказа")
        finished_stock_id_value = parse_int(finished_stock_id, "Партия готовой продукции")
        quantity_value = parse_decimal(quantity, "Количество")
        if quantity_value <= 0:
            raise ValueError("Количество должно быть больше нуля.")

        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            ensure_order_paid_for_shipping(conn, shipment["order_id"])
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
                    SELECT
                        fgs.finished_stock_id,
                        fgs.product_id,
                        fgs.quantity_current,
                        fgs.expiry_date,
                        fgs.production_batch_id
                    FROM finished_goods_stock AS fgs
                    WHERE fgs.finished_stock_id = %s
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
                    raise ValueError("Недостаточно готовой продукции.")

                validate_finished_batch_quality(cur, stock["production_batch_id"])

                cur.execute(
                    """
                    SELECT COALESCE(SUM(quantity), 0) AS shipped_quantity
                    FROM shipment_items
                    WHERE order_item_id = %s
                    """,
                    (order_item_id_value,),
                )
                shipped = cur.fetchone()
                if Decimal(shipped["shipped_quantity"]) + quantity_value > Decimal(order_item["quantity"]):
                    raise ValueError("Количество отгрузки превышает объём заказа.")

                cur.execute(
                    """
                    INSERT INTO shipment_items (
                        shipment_id, order_item_id, product_id, finished_stock_id, quantity
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
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
                      AND quantity_current >= %s
                    """,
                    (quantity_value, finished_stock_id_value, quantity_value),
                )
                if cur.rowcount != 1:
                    raise ValueError("Не удалось корректно списать готовую продукцию со склада.")
        set_flash(request, "Позиция отгрузки успешно добавлена, остаток готовой продукции уменьшен.")
        return redirect_to(f"/shipments/{shipment_id}")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "Не удалось сохранить позицию отгрузки."

    return render_template(
        request,
        "form.html",
        {
            "title": f"Добавить позицию в отгрузку #{shipment_id}",
            "action": f"/shipments/{shipment_id}/items/new",
            "fields": shipment_item_fields(order_items, finished_stock, form_data),
            "back_url": f"/shipments/{shipment_id}",
            "submit_label": "Добавить позицию",
            "error_message": error_message,
        },
        status_code=400,
    )


@router.get("/shipments/{shipment_id}/status")
def shipment_status_page(request: Request, shipment_id: int):
    user = authorize_action(request, "shipments.change_status", "У вас нет прав на изменение статуса отгрузки.")
    if not isinstance(user, dict):
        return user
    shipment = fetch_shipment_for_user(shipment_id, user)
    if not shipment:
        return render_template(request, "error.html", {"title": "Отгрузка не найдена", "message": "Карточка отгрузки не найдена."}, status_code=404)
    statuses = fetch_shipment_status_options(shipment)
    if not statuses:
        return forbidden_response(request, "Для текущего статуса отгрузки нет допустимых переходов.")
    return render_template(
        request,
        "form.html",
        {
            "title": f"Изменить статус отгрузки #{shipment_id}",
            "action": f"/shipments/{shipment_id}/status",
            "fields": shipment_status_fields(statuses, statuses[0]["status_code"]),
            "back_url": f"/shipments/{shipment_id}",
            "submit_label": "Обновить статус",
        },
    )


@router.post("/shipments/{shipment_id}/status")
def shipment_status_update(request: Request, shipment_id: int, status_code: str = Form(...)):
    user = authorize_action(request, "shipments.change_status", "У вас нет прав на изменение статуса отгрузки.")
    if not isinstance(user, dict):
        return user
    shipment = fetch_shipment_for_user(shipment_id, user)
    if not shipment:
        return render_template(request, "error.html", {"title": "Отгрузка не найдена", "message": "Карточка отгрузки не найдена."}, status_code=404)
    statuses = fetch_shipment_status_options(shipment)
    try:
        new_status = clean_text(status_code)
        if not new_status:
            raise ValueError("Не выбран новый статус отгрузки.")
        validate_shipment_status_change(shipment, new_status)
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            if new_status == "shipped":
                ensure_order_paid_for_shipping(conn, shipment["order_id"])
                ensure_shipment_has_items(conn, shipment_id)
            elif new_status == "delivered":
                ensure_shipment_has_items(conn, shipment_id)

            with conn.cursor() as cur:
                if new_status == "shipped":
                    cur.execute(
                        """
                        UPDATE shipments
                        SET status_code = %s,
                            shipped_at = COALESCE(shipped_at, CURRENT_TIMESTAMP)
                        WHERE shipment_id = %s
                        """,
                        (new_status, shipment_id),
                    )
                else:
                    cur.execute("UPDATE shipments SET status_code = %s WHERE shipment_id = %s", (new_status, shipment_id))
        set_flash(request, "Статус отгрузки успешно обновлён.")
        return redirect_to(f"/shipments/{shipment_id}")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "Не удалось изменить статус отгрузки."

    return render_template(
        request,
        "form.html",
        {
            "title": f"Изменить статус отгрузки #{shipment_id}",
            "action": f"/shipments/{shipment_id}/status",
            "fields": shipment_status_fields(statuses, clean_text(status_code) or shipment["status_code"]),
            "back_url": f"/shipments/{shipment_id}",
            "submit_label": "Обновить статус",
            "error_message": error_message,
        },
        status_code=400,
    )


@router.get("/shipments/{shipment_id}/report")
def shipment_report(request: Request, shipment_id: int):
    user = authorize_action(request, "shipments.report", "У вас нет прав на просмотр отчёта по отгрузке.")
    if not isinstance(user, dict):
        return user
    shipment = fetch_shipment_for_user(shipment_id, user)
    if not shipment:
        return render_template(request, "error.html", {"title": "Отгрузка не найдена", "message": "Отчёт по этой отгрузке недоступен."}, status_code=404)

    report = fetch_one(
        """
        SELECT
            s.shipment_id,
            s.shipment_number,
            s.shipped_at,
            s.status_code,
            s.delivery_address,
            s.waybill_number,
            s.note,
            o.order_number,
            COALESCE(c.company_name, c.full_name) AS customer_name,
            u.full_name AS employee_name
        FROM shipments AS s
        JOIN customer_orders AS o ON o.order_id = s.order_id
        JOIN customers AS c ON c.customer_id = o.customer_id
        LEFT JOIN users AS u ON u.user_id = s.created_by_user_id
        WHERE s.shipment_id = %s
        """,
        (shipment_id,),
    )
    items = fetch_all(
        """
        SELECT
            p.name AS product_name,
            si.order_item_id,
            fgs.batch_number,
            si.quantity,
            p.unit,
            fgs.expiry_date
        FROM shipment_items AS si
        JOIN products AS p ON p.product_id = si.product_id
        LEFT JOIN finished_goods_stock AS fgs ON fgs.finished_stock_id = si.finished_stock_id
        WHERE si.shipment_id = %s
        ORDER BY si.shipment_item_id
        """,
        (shipment_id,),
    )
    total_quantity = sum(Decimal(row["quantity"]) for row in items) if items else Decimal("0")
    return render_template(
        request,
        "shipment_report.html",
        {
            "title": f"Отчёт по отгрузке {report['shipment_number']}",
            "back_url": f"/shipments/{shipment_id}",
            "shipment": report,
            "items": items,
            "total_quantity": total_quantity,
        },
    )
