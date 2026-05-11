from fastapi import APIRouter, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_action, authorize_section, redirect_to, render_template, set_flash
from ..database import fetch_all, fetch_one, get_db
from ..permissions import has_action


router = APIRouter()

SUPPLIER_INVOICE_PAYABLE_STATUSES = {"issued", "overdue"}


def fetch_supplier_invoice(supplier_invoice_id: int):
    return fetch_one(
        """
        SELECT
            si.supplier_invoice_id,
            si.supplier_invoice_number,
            si.delivery_id,
            si.supplier_id,
            si.issue_date,
            si.due_date,
            si.paid_at,
            si.amount,
            si.status_code,
            si.document_ref,
            si.note,
            s.company_name,
            d.delivery_number,
            d.status_code AS delivery_status_code
        FROM supplier_invoices AS si
        JOIN suppliers AS s ON s.supplier_id = si.supplier_id
        JOIN raw_material_deliveries AS d ON d.delivery_id = si.delivery_id
        WHERE si.supplier_invoice_id = %s
        """,
        (supplier_invoice_id,),
    )


def update_supplier_invoice_status(conn, supplier_invoice_id: int, new_status: str):
    with conn.cursor() as cur:
        if new_status == "paid":
            cur.execute(
                """
                UPDATE supplier_invoices
                SET status_code = 'paid',
                    paid_at = CURRENT_TIMESTAMP
                WHERE supplier_invoice_id = %s
                RETURNING supplier_invoice_id
                """,
                (supplier_invoice_id,),
            )
        else:
            cur.execute(
                """
                UPDATE supplier_invoices
                SET status_code = %s,
                    paid_at = NULL
                WHERE supplier_invoice_id = %s
                RETURNING supplier_invoice_id
                """,
                (new_status, supplier_invoice_id),
            )
        if not cur.fetchone():
            raise ValueError("Счёт поставщика не найден.")


@router.get("/supplier-invoices")
def supplier_invoices_list(request: Request):
    user = authorize_section(request, "supplier_invoices")
    if not isinstance(user, dict):
        return user

    rows = fetch_all(
        """
        SELECT
            si.supplier_invoice_id,
            si.supplier_invoice_number,
            s.company_name,
            d.delivery_number,
            si.issue_date,
            si.due_date,
            si.amount,
            si.status_code,
            si.paid_at
        FROM supplier_invoices AS si
        JOIN suppliers AS s ON s.supplier_id = si.supplier_id
        JOIN raw_material_deliveries AS d ON d.delivery_id = si.delivery_id
        ORDER BY si.issue_date DESC, si.supplier_invoice_id DESC
        """
    )
    for row in rows:
        row["_detail_url"] = f"/supplier-invoices/{row['supplier_invoice_id']}"
        if has_action(user, "supplier_invoices.pay") and row["status_code"] in SUPPLIER_INVOICE_PAYABLE_STATUSES:
            row["_row_forms"] = [
                {
                    "action": f"/supplier-invoices/{row['supplier_invoice_id']}/pay",
                    "label": "Оплатить",
                    "class": "btn-outline-success",
                }
            ]

    return render_template(
        request,
        "table_list.html",
        {
            "title": "Счета поставщиков",
            "subtitle": "Счета, полученные от поставщиков по принятым поставкам сырья.",
            "headers": [
                ("supplier_invoice_id", "ID"),
                ("supplier_invoice_number", "Номер счёта"),
                ("company_name", "Поставщик"),
                ("delivery_number", "Поставка"),
                ("issue_date", "Дата выставления"),
                ("due_date", "Срок оплаты"),
                ("amount", "Сумма"),
                ("status_code", "Статус"),
                ("paid_at", "Дата оплаты"),
            ],
            "rows": rows,
        },
    )


@router.get("/supplier-invoices/{supplier_invoice_id}")
def supplier_invoice_detail(request: Request, supplier_invoice_id: int):
    user = authorize_section(request, "supplier_invoices")
    if not isinstance(user, dict):
        return user

    supplier_invoice = fetch_supplier_invoice(supplier_invoice_id)
    if not supplier_invoice:
        return render_template(
            request,
            "error.html",
            {"title": "Счёт поставщика не найден", "message": "Карточка счёта поставщика не найдена."},
            status_code=404,
        )

    extra_forms = []
    if has_action(user, "supplier_invoices.pay") and supplier_invoice["status_code"] in SUPPLIER_INVOICE_PAYABLE_STATUSES:
        extra_forms.append(
            {
                "action": f"/supplier-invoices/{supplier_invoice_id}/pay",
                "label": "Оплатить",
                "class": "btn-outline-success",
            }
        )

    return render_template(
        request,
        "detail.html",
        {
            "title": supplier_invoice["supplier_invoice_number"],
            "back_url": "/supplier-invoices",
            "extra_forms": extra_forms,
            "details": [
                ("ID", supplier_invoice["supplier_invoice_id"]),
                ("Поставщик", supplier_invoice["company_name"]),
                ("Номер поставки", supplier_invoice["delivery_number"]),
                ("Статус поставки", supplier_invoice["delivery_status_code"]),
                ("Дата выставления", supplier_invoice["issue_date"]),
                ("Срок оплаты", supplier_invoice["due_date"]),
                ("Сумма", supplier_invoice["amount"]),
                ("Статус счёта", supplier_invoice["status_code"]),
                ("Дата оплаты", supplier_invoice["paid_at"]),
                ("Документ", supplier_invoice["document_ref"]),
                ("Примечание", supplier_invoice["note"]),
            ],
        },
    )


@router.post("/supplier-invoices/{supplier_invoice_id}/pay")
def supplier_invoice_pay(request: Request, supplier_invoice_id: int):
    user = authorize_action(request, "supplier_invoices.pay", "У вас нет прав на оплату счетов поставщиков.")
    if not isinstance(user, dict):
        return user

    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT supplier_invoice_id, status_code
                    FROM supplier_invoices
                    WHERE supplier_invoice_id = %s
                    FOR UPDATE
                    """,
                    (supplier_invoice_id,),
                )
                supplier_invoice = cur.fetchone()
                if not supplier_invoice:
                    raise ValueError("Счёт поставщика не найден.")
                if supplier_invoice["status_code"] == "paid":
                    raise ValueError("Счёт поставщика уже оплачен.")
                if supplier_invoice["status_code"] not in SUPPLIER_INVOICE_PAYABLE_STATUSES:
                    raise ValueError("Этот счёт поставщика нельзя оплатить в текущем статусе.")

            update_supplier_invoice_status(conn, supplier_invoice_id, "paid")

        set_flash(request, "Счёт поставщика успешно оплачен.")
    except ValueError as exc:
        set_flash(request, str(exc), "danger")
    except PsycopgError:
        set_flash(request, "Не удалось оплатить счёт поставщика. Попробуйте снова.", "danger")

    return redirect_to("/supplier-invoices")
