from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_action, authorize_section, forbidden_response, redirect_to, render_template, set_flash
from ..database import fetch_all, fetch_one, get_db
from ..permissions import has_action
from ..utils import build_options, clean_text, parse_date


router = APIRouter()

INVOICE_STATUS_TRANSITIONS = {
    "issued": {"paid", "overdue"},
    "overdue": {"paid"},
    "paid": set(),
    "cancelled": set(),
}


def invoice_fields(orders, data=None):
    data = data or {}
    return [
        {"name": "order_id", "label": "Заказ", "type": "select", "required": True, "value": data.get("order_id", ""), "options": build_options(orders, "order_id", "display_name")},
        {"name": "issue_date", "label": "Дата выставления", "type": "date", "required": True, "value": data.get("issue_date", "")},
        {"name": "due_date", "label": "Срок оплаты", "type": "date", "value": data.get("due_date", "")},
        {"name": "note", "label": "Примечание", "type": "textarea", "value": data.get("note", "")},
    ]


def invoice_status_fields(statuses, current_status):
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


def fetch_invoice_for_user(invoice_id: int, user: dict):
    query = """
        SELECT
            i.invoice_id,
            i.invoice_number,
            i.order_id,
            i.issue_date,
            i.due_date,
            i.paid_at,
            i.amount,
            i.status_code,
            i.note,
            o.order_number,
            o.customer_id
        FROM invoices AS i
        JOIN customer_orders AS o ON o.order_id = i.order_id
        WHERE i.invoice_id = %s
    """
    params = [invoice_id]
    if "client" in user.get("roles", []):
        query += " AND o.customer_id = %s"
        params.append(user["customer_id"])
    return fetch_one(query, tuple(params))


def get_invoice_orders():
    return fetch_all(
        """
        SELECT o.order_id, o.order_number || ' / ' || o.status_code AS display_name
        FROM customer_orders AS o
        WHERE o.status_code IN ('confirmed', 'in_production', 'ready', 'shipped', 'completed')
          AND NOT EXISTS (
              SELECT 1
              FROM invoices AS i
              WHERE i.order_id = o.order_id
                AND i.status_code IN ('issued', 'overdue', 'paid')
          )
        ORDER BY o.order_id DESC
        """
    )


def get_next_invoice_statuses(invoice: dict) -> list[str]:
    return sorted(INVOICE_STATUS_TRANSITIONS.get(invoice["status_code"], set()))


def fetch_invoice_status_options(invoice: dict):
    next_statuses = get_next_invoice_statuses(invoice)
    if not next_statuses:
        return []
    return fetch_all(
        """
        SELECT status_code, name
        FROM invoice_statuses
        WHERE status_code = ANY(%s)
        ORDER BY name
        """,
        (next_statuses,),
    )


def validate_invoice_status_change(invoice: dict, new_status: str):
    if new_status not in INVOICE_STATUS_TRANSITIONS.get(invoice["status_code"], set()):
        raise ValueError("Недопустимый переход статуса счёта.")


def update_invoice_status(conn, invoice_id: int, new_status: str):
    with conn.cursor() as cur:
        if new_status == "paid":
            cur.execute(
                """
                UPDATE invoices
                SET status_code = 'paid',
                    paid_at = CURRENT_TIMESTAMP
                WHERE invoice_id = %s
                RETURNING invoice_id
                """,
                (invoice_id,),
            )
        else:
            cur.execute(
                """
                UPDATE invoices
                SET status_code = %s,
                    paid_at = NULL
                WHERE invoice_id = %s
                RETURNING invoice_id
                """,
                (new_status, invoice_id),
            )
        if not cur.fetchone():
            raise ValueError("Счёт не найден или недоступен для изменения.")


@router.get("/invoices")
def invoices_list(request: Request):
    user = authorize_section(request, "invoices")
    if not isinstance(user, dict):
        return user
    query = """
        SELECT
            i.invoice_id,
            i.invoice_number,
            o.order_number,
            i.issue_date,
            i.due_date,
            i.paid_at,
            i.amount,
            i.status_code
        FROM invoices AS i
        JOIN customer_orders AS o ON o.order_id = i.order_id
    """
    params = ()
    if "client" in user.get("roles", []):
        query += " WHERE o.customer_id = %s "
        params = (user["customer_id"],)
    query += " ORDER BY i.issue_date DESC, i.invoice_id DESC"
    rows = fetch_all(query, params)
    for row in rows:
        if has_action(user, "invoices.change_status"):
            row["_detail_url"] = f"/invoices/{row['invoice_id']}/status"
        elif has_action(user, "invoices.pay_own") and row["status_code"] in {"issued", "overdue"}:
            row["_row_forms"] = [
                {
                    "action": f"/invoices/{row['invoice_id']}/pay",
                    "label": "Оплатить",
                    "class": "btn-outline-success",
                }
            ]
    context = {
        "title": "Счета",
        "subtitle": "Счета, связанные с заказами клиентов.",
        "headers": [
            ("invoice_id", "ID"),
            ("invoice_number", "Номер счёта"),
            ("order_number", "Номер заказа"),
            ("issue_date", "Дата выставления"),
            ("due_date", "Срок оплаты"),
            ("paid_at", "Дата оплаты"),
            ("amount", "Сумма"),
            ("status_code", "Статус"),
        ],
        "rows": rows,
    }
    if has_action(user, "invoices.create"):
        context["create_url"] = "/invoices/new"
        context["create_label"] = "Создать счёт"
    return render_template(request, "table_list.html", context)


@router.get("/invoices/new")
def invoice_new_page(request: Request):
    user = authorize_action(request, "invoices.create", "У вас нет прав на создание счетов.")
    if not isinstance(user, dict):
        return user
    return render_template(
        request,
        "form.html",
        {
            "title": "Создать счёт",
            "action": "/invoices/new",
            "fields": invoice_fields(get_invoice_orders()),
            "back_url": "/invoices",
            "submit_label": "Создать счёт",
        },
    )


@router.post("/invoices/new")
def invoice_new(
    request: Request,
    order_id: str = Form(...),
    issue_date: str = Form(...),
    due_date: str = Form(""),
    note: str = Form(""),
):
    user = authorize_action(request, "invoices.create", "У вас нет прав на создание счетов.")
    if not isinstance(user, dict):
        return user
    form_data = {"order_id": order_id, "issue_date": issue_date, "due_date": due_date, "note": note}
    orders = get_invoice_orders()
    try:
        order_id_value = int(order_id)
        issue_date_value = parse_date(issue_date, "Дата выставления")
        due_date_value = parse_date(due_date, "Срок оплаты", allow_none=True)
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT order_id, status_code
                    FROM customer_orders
                    WHERE order_id = %s
                    """,
                    (order_id_value,),
                )
                order = cur.fetchone()
                if not order:
                    raise ValueError("Выбранный заказ не существует.")
                if order["status_code"] == "draft":
                    raise ValueError("Нельзя создать счёт по заказу со статусом «Черновик».")

                cur.execute(
                    """
                    SELECT COUNT(*) AS items_count, COALESCE(SUM(line_amount), 0) AS total_amount
                    FROM order_items
                    WHERE order_id = %s
                    """,
                    (order_id_value,),
                )
                amount_row = cur.fetchone()
                if not amount_row or amount_row["items_count"] <= 0:
                    raise ValueError("Нельзя создать счёт для пустого заказа.")
                if amount_row["total_amount"] <= 0:
                    raise ValueError("Сумма счёта должна быть больше нуля.")

                cur.execute(
                    """
                    SELECT 1
                    FROM invoices
                    WHERE order_id = %s
                      AND status_code IN ('issued', 'overdue', 'paid')
                    LIMIT 1
                    """,
                    (order_id_value,),
                )
                if cur.fetchone():
                    raise ValueError("По этому заказу уже существует счёт.")

                cur.execute(
                    """
                    WITH new_invoice AS (
                        SELECT nextval(pg_get_serial_sequence('invoices', 'invoice_id')) AS invoice_id
                    )
                    INSERT INTO invoices (
                        invoice_id, invoice_number, order_id, issue_date, due_date, amount, status_code, note
                    )
                    SELECT
                        new_invoice.invoice_id,
                        'INV-WEB-' || LPAD(new_invoice.invoice_id::TEXT, 4, '0'),
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    FROM new_invoice
                    """,
                    (
                        order_id_value,
                        issue_date_value,
                        due_date_value,
                        amount_row["total_amount"],
                        "issued",
                        clean_text(note),
                    ),
                )
        set_flash(request, "Счёт успешно создан. Сумма рассчитана по позициям заказа.")
        return redirect_to("/invoices")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "Не удалось создать счёт. Проверьте данные и попробуйте снова."

    return render_template(
        request,
        "form.html",
        {
            "title": "Создать счёт",
            "action": "/invoices/new",
            "fields": invoice_fields(orders, form_data),
            "back_url": "/invoices",
            "submit_label": "Создать счёт",
            "error_message": error_message,
        },
        status_code=400,
    )


@router.post("/invoices/{invoice_id}/pay")
def invoice_pay(request: Request, invoice_id: int):
    user = authorize_action(request, "invoices.pay_own", "У вас нет прав на оплату этого счёта.")
    if not isinstance(user, dict):
        return user

    invoice = fetch_invoice_for_user(invoice_id, user)
    if not invoice:
        return forbidden_response(request, "Счёт не найден или недоступен.")

    try:
        if "client" not in user.get("roles", []):
            return forbidden_response(request, "Оплачивать счёт через этот маршрут может только клиент.")
        if invoice["customer_id"] != user.get("customer_id"):
            return forbidden_response(request, "Нельзя оплатить чужой счёт.")
        if invoice["status_code"] == "paid":
            raise ValueError("Счёт уже оплачен.")
        if invoice["status_code"] not in {"issued", "overdue"}:
            raise ValueError("Этот счёт нельзя оплатить в текущем статусе.")

        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT i.invoice_id, i.status_code, o.customer_id
                    FROM invoices AS i
                    JOIN customer_orders AS o ON o.order_id = i.order_id
                    WHERE i.invoice_id = %s
                    FOR UPDATE
                    """,
                    (invoice_id,),
                )
                locked_invoice = cur.fetchone()
                if not locked_invoice:
                    raise ValueError("Счёт не найден.")
                if locked_invoice["customer_id"] != user.get("customer_id"):
                    return forbidden_response(request, "Нельзя оплатить чужой счёт.")
                if locked_invoice["status_code"] == "paid":
                    raise ValueError("Счёт уже оплачен.")
                if locked_invoice["status_code"] not in {"issued", "overdue"}:
                    raise ValueError("Этот счёт нельзя оплатить в текущем статусе.")

            update_invoice_status(conn, invoice_id, "paid")

        set_flash(request, "Счёт успешно оплачен.")
        return redirect_to("/invoices")
    except ValueError as exc:
        set_flash(request, str(exc), "danger")
        return redirect_to("/invoices")
    except PsycopgError:
        set_flash(request, "Не удалось оплатить счёт. Попробуйте снова.", "danger")
        return redirect_to("/invoices")


@router.get("/invoices/{invoice_id}/status")
def invoice_status_page(request: Request, invoice_id: int):
    user = authorize_action(request, "invoices.change_status", "У вас нет прав на изменение статуса счёта.")
    if not isinstance(user, dict):
        return user
    invoice = fetch_invoice_for_user(invoice_id, user)
    if not invoice:
        return render_template(request, "error.html", {"title": "Счёт не найден", "message": "Карточка счёта не найдена."}, status_code=404)
    statuses = fetch_invoice_status_options(invoice)
    if not statuses:
        return render_template(request, "error.html", {"title": "Изменение недоступно", "message": "Для текущего статуса счёта нет допустимых переходов."}, status_code=403)
    return render_template(
        request,
        "form.html",
        {
            "title": f"Изменить статус счёта #{invoice_id}",
            "action": f"/invoices/{invoice_id}/status",
            "fields": invoice_status_fields(statuses, statuses[0]["status_code"]),
            "back_url": "/invoices",
            "submit_label": "Обновить статус",
        },
    )


@router.post("/invoices/{invoice_id}/status")
def invoice_status_update(request: Request, invoice_id: int, status_code: str = Form(...)):
    user = authorize_action(request, "invoices.change_status", "У вас нет прав на изменение статуса счёта.")
    if not isinstance(user, dict):
        return user
    invoice = fetch_invoice_for_user(invoice_id, user)
    if not invoice:
        return render_template(request, "error.html", {"title": "Счёт не найден", "message": "Карточка счёта не найдена."}, status_code=404)
    statuses = fetch_invoice_status_options(invoice)
    try:
        new_status = clean_text(status_code)
        if not new_status:
            raise ValueError("Не выбран новый статус счёта.")
        validate_invoice_status_change(invoice, new_status)
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            update_invoice_status(conn, invoice_id, new_status)
        set_flash(request, "Статус счёта успешно обновлён.")
        return redirect_to("/invoices")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "Не удалось изменить статус счёта."

    return render_template(
        request,
        "form.html",
        {
            "title": f"Изменить статус счёта #{invoice_id}",
            "action": f"/invoices/{invoice_id}/status",
            "fields": invoice_status_fields(statuses, clean_text(status_code) or invoice["status_code"]),
            "back_url": "/invoices",
            "submit_label": "Обновить статус",
            "error_message": error_message,
        },
        status_code=400,
    )
