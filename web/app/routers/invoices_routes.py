from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_section, redirect_to, render_template, set_flash
from ..database import fetch_all, get_db, next_id
from ..utils import build_options, clean_text, parse_date, parse_decimal


router = APIRouter()


def invoice_fields(orders, statuses, data=None):
    data = data or {}
    return [
        {"name": "order_id", "label": "Order", "type": "select", "required": True, "value": data.get("order_id", ""), "options": build_options(orders, "order_id", "display_name")},
        {"name": "issue_date", "label": "Issue Date", "type": "date", "required": True, "value": data.get("issue_date", "")},
        {"name": "due_date", "label": "Due Date", "type": "date", "value": data.get("due_date", "")},
        {"name": "amount", "label": "Amount", "type": "number", "required": True, "step": "0.01", "min": "0", "value": data.get("amount", "")},
        {"name": "status_code", "label": "Status", "type": "select", "required": True, "value": data.get("status_code", "issued"), "options": build_options(statuses, "status_code", "name")},
        {"name": "note", "label": "Note", "type": "textarea", "value": data.get("note", "")},
    ]


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
        if "client" not in user.get("roles", []):
            row["_detail_url"] = f"/invoices/{row['invoice_id']}/status"
    context = {
        "title": "Invoices",
        "subtitle": "Invoices linked to customer orders.",
        "headers": [
            ("invoice_id", "ID"),
            ("invoice_number", "Invoice Number"),
            ("order_number", "Order Number"),
            ("issue_date", "Issue Date"),
            ("due_date", "Due Date"),
            ("paid_at", "Paid At"),
            ("amount", "Amount"),
            ("status_code", "Status"),
        ],
        "rows": rows,
    }
    if "client" not in user.get("roles", []):
        context["create_url"] = "/invoices/new"
        context["create_label"] = "Create Invoice"
    return render_template(request, "table_list.html", context)


@router.get("/invoices/new")
def invoice_new_page(request: Request):
    user = authorize_section(request, "invoices")
    if not isinstance(user, dict):
        return user
    if "client" in user.get("roles", []):
        return render_template(request, "error.html", {"title": "Access denied", "message": "Clients can only view invoices."}, status_code=403)
    orders = fetch_all("SELECT order_id, order_number || ' / ' || status_code AS display_name FROM customer_orders ORDER BY order_id DESC")
    statuses = fetch_all("SELECT status_code, name FROM invoice_statuses ORDER BY name")
    return render_template(request, "form.html", {"title": "Create Invoice", "action": "/invoices/new", "fields": invoice_fields(orders, statuses), "back_url": "/invoices", "submit_label": "Create Invoice"})


@router.post("/invoices/new")
def invoice_new(
    request: Request,
    order_id: str = Form(...),
    issue_date: str = Form(...),
    due_date: str = Form(""),
    amount: str = Form(...),
    status_code: str = Form(...),
    note: str = Form(""),
):
    user = authorize_section(request, "invoices")
    if not isinstance(user, dict):
        return user
    if "client" in user.get("roles", []):
        return render_template(request, "error.html", {"title": "Access denied", "message": "Clients can only view invoices."}, status_code=403)
    orders = fetch_all("SELECT order_id, order_number || ' / ' || status_code AS display_name FROM customer_orders ORDER BY order_id DESC")
    statuses = fetch_all("SELECT status_code, name FROM invoice_statuses ORDER BY name")
    form_data = {"order_id": order_id, "issue_date": issue_date, "due_date": due_date, "amount": amount, "status_code": status_code, "note": note}
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            invoice_id = next_id(conn, "invoices", "invoice_id")
            invoice_number = f"INV-WEB-{invoice_id:04d}"
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO invoices (
                        invoice_id, invoice_number, order_id, issue_date, due_date, amount, status_code, note
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        invoice_id,
                        invoice_number,
                        int(order_id),
                        parse_date(issue_date, "Issue Date"),
                        parse_date(due_date, "Due Date", allow_none=True),
                        parse_decimal(amount, "Amount"),
                        clean_text(status_code),
                        clean_text(note),
                    ),
                )
        set_flash(request, "Invoice created successfully.")
        return redirect_to("/invoices")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": "Create Invoice", "action": "/invoices/new", "fields": invoice_fields(orders, statuses, form_data), "back_url": "/invoices", "submit_label": "Create Invoice", "error_message": str(exc)}, status_code=400)


@router.get("/invoices/{invoice_id}/status")
def invoice_status_page(request: Request, invoice_id: int):
    user = authorize_section(request, "invoices")
    if not isinstance(user, dict):
        return user
    if "client" in user.get("roles", []):
        return render_template(request, "error.html", {"title": "Access denied", "message": "Clients can only view invoices."}, status_code=403)
    invoice = fetch_all("SELECT invoice_id, status_code FROM invoices WHERE invoice_id = %s", (invoice_id,))
    if not invoice:
        return render_template(request, "error.html", {"title": "Invoice not found", "message": "Invoice record not found."}, status_code=404)
    statuses = fetch_all("SELECT status_code, name FROM invoice_statuses ORDER BY name")
    return render_template(request, "form.html", {"title": f"Change Status for Invoice #{invoice_id}", "action": f"/invoices/{invoice_id}/status", "fields": [{"name": "status_code", "label": "Status", "type": "select", "required": True, "value": invoice[0]['status_code'], "options": build_options(statuses, 'status_code', 'name')}], "back_url": "/invoices", "submit_label": "Update Status"})


@router.post("/invoices/{invoice_id}/status")
def invoice_status_update(request: Request, invoice_id: int, status_code: str = Form(...)):
    user = authorize_section(request, "invoices")
    if not isinstance(user, dict):
        return user
    if "client" in user.get("roles", []):
        return render_template(request, "error.html", {"title": "Access denied", "message": "Clients can only view invoices."}, status_code=403)
    statuses = fetch_all("SELECT status_code, name FROM invoice_statuses ORDER BY name")
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                if status_code == "paid":
                    cur.execute("UPDATE invoices SET status_code = %s, paid_at = CURRENT_TIMESTAMP WHERE invoice_id = %s", (clean_text(status_code), invoice_id))
                else:
                    cur.execute("UPDATE invoices SET status_code = %s WHERE invoice_id = %s", (clean_text(status_code), invoice_id))
        set_flash(request, "Invoice status updated successfully.")
        return redirect_to("/invoices")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"Change Status for Invoice #{invoice_id}", "action": f"/invoices/{invoice_id}/status", "fields": [{"name": "status_code", "label": "Status", "type": "select", "required": True, "value": status_code, "options": build_options(statuses, 'status_code', 'name')}], "back_url": "/invoices", "submit_label": "Update Status", "error_message": str(exc)}, status_code=400)
