from datetime import date, timedelta

from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_section, redirect_to, render_template, set_flash
from ..database import fetch_all, get_db, next_id
from ..utils import build_options, clean_text, parse_date, parse_datetime_local, parse_decimal, parse_int


router = APIRouter()


def production_fields(products, tech_cards, users, statuses, data=None):
    data = data or {}
    return [
        {"name": "product_id", "label": "Product", "type": "select", "required": True, "value": data.get("product_id", ""), "options": build_options(products, "product_id", "name")},
        {"name": "tech_card_id", "label": "Tech Card", "type": "select", "required": True, "value": data.get("tech_card_id", ""), "options": build_options(tech_cards, "tech_card_id", "card_label")},
        {"name": "production_date", "label": "Production Date", "type": "datetime-local", "required": True, "value": data.get("production_date", "")},
        {"name": "shift", "label": "Shift", "type": "text", "value": data.get("shift", "")},
        {"name": "quantity_produced", "label": "Quantity Produced", "type": "number", "required": True, "step": "0.001", "min": "0.001", "value": data.get("quantity_produced", "")},
        {"name": "quantity_defective", "label": "Quantity Defective", "type": "number", "step": "0.001", "min": "0", "value": data.get("quantity_defective", "0")},
        {"name": "responsible_user_id", "label": "Responsible User", "type": "select", "value": data.get("responsible_user_id", ""), "options": build_options(users, "user_id", "full_name", blank_label="Select user")},
        {"name": "status_code", "label": "Status", "type": "select", "required": True, "value": data.get("status_code", "planned"), "options": build_options(statuses, "status_code", "name")},
        {"name": "note", "label": "Note", "type": "textarea", "value": data.get("note", "")},
    ]


@router.get("/production")
def production_list(request: Request):
    user = authorize_section(request, "production")
    if not isinstance(user, dict):
        return user
    rows = fetch_all(
        """
        SELECT
            pb.production_batch_id,
            pb.batch_number,
            p.name AS product_name,
            tc.card_number,
            pb.production_date,
            pb.quantity_produced,
            pb.quantity_defective,
            pb.status_code
        FROM production_batches AS pb
        JOIN products AS p ON p.product_id = pb.product_id
        JOIN tech_cards AS tc ON tc.tech_card_id = pb.tech_card_id
        ORDER BY pb.production_date DESC, pb.production_batch_id DESC
        """
    )
    return render_template(
        request,
        "table_list.html",
        {
            "title": "Production Batches",
            "subtitle": "Production journal entries for finished goods.",
            "headers": [
                ("production_batch_id", "ID"),
                ("batch_number", "Batch Number"),
                ("product_name", "Product"),
                ("card_number", "Tech Card"),
                ("production_date", "Production Date"),
                ("quantity_produced", "Produced"),
                ("quantity_defective", "Defective"),
                ("status_code", "Status"),
            ],
            "rows": rows,
            "create_url": "/production/new",
            "create_label": "Add Production Batch",
        },
    )


@router.get("/production/new")
def production_new_page(request: Request):
    user = authorize_section(request, "production")
    if not isinstance(user, dict):
        return user
    products = fetch_all("SELECT product_id, name FROM products WHERE is_active = TRUE ORDER BY name")
    tech_cards = fetch_all("SELECT tech_card_id, card_number || ' / ' || version::TEXT AS card_label FROM tech_cards ORDER BY card_number")
    users = fetch_all("SELECT user_id, full_name FROM users WHERE status_code = 'active' ORDER BY full_name")
    statuses = fetch_all("SELECT status_code, name FROM production_statuses ORDER BY name")
    return render_template(request, "form.html", {"title": "Add Production Batch", "action": "/production/new", "fields": production_fields(products, tech_cards, users, statuses), "back_url": "/production", "submit_label": "Create Production Batch"})


@router.post("/production/new")
def production_new(
    request: Request,
    product_id: str = Form(...),
    tech_card_id: str = Form(...),
    production_date: str = Form(...),
    shift: str = Form(""),
    quantity_produced: str = Form(...),
    quantity_defective: str = Form("0"),
    responsible_user_id: str = Form(""),
    status_code: str = Form(...),
    note: str = Form(""),
):
    user = authorize_section(request, "production")
    if not isinstance(user, dict):
        return user
    products = fetch_all("SELECT product_id, name FROM products WHERE is_active = TRUE ORDER BY name")
    tech_cards = fetch_all("SELECT tech_card_id, card_number || ' / ' || version::TEXT AS card_label FROM tech_cards ORDER BY card_number")
    users = fetch_all("SELECT user_id, full_name FROM users WHERE status_code = 'active' ORDER BY full_name")
    statuses = fetch_all("SELECT status_code, name FROM production_statuses ORDER BY name")
    form_data = {"product_id": product_id, "tech_card_id": tech_card_id, "production_date": production_date, "shift": shift, "quantity_produced": quantity_produced, "quantity_defective": quantity_defective, "responsible_user_id": responsible_user_id, "status_code": status_code, "note": note}
    try:
        production_dt = parse_datetime_local(production_date, "Production Date")
        produced_qty = parse_decimal(quantity_produced, "Quantity Produced")
        defective_qty = parse_decimal(quantity_defective, "Quantity Defective")
        product_id_value = parse_int(product_id, "Product")
        tech_card_id_value = parse_int(tech_card_id, "Tech Card")
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            production_batch_id = next_id(conn, "production_batches", "production_batch_id")
            finished_stock_id = next_id(conn, "finished_goods_stock", "finished_stock_id")
            batch_number = f"PB-WEB-{production_batch_id:04d}"
            with conn.cursor() as cur:
                cur.execute("SELECT shelf_life_days FROM products WHERE product_id = %s", (product_id_value,))
                product_row = cur.fetchone()
                if not product_row:
                    raise ValueError("Selected product does not exist.")
                expiry_dt = production_dt.date() + timedelta(days=product_row["shelf_life_days"])
                cur.execute(
                    """
                    INSERT INTO production_batches (
                        production_batch_id, batch_number, product_id, tech_card_id, production_date,
                        shift, quantity_produced, quantity_defective, responsible_user_id, status_code, note
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        production_batch_id,
                        batch_number,
                        product_id_value,
                        tech_card_id_value,
                        production_dt,
                        clean_text(shift),
                        produced_qty,
                        defective_qty,
                        parse_int(responsible_user_id, "Responsible User", allow_none=True),
                        clean_text(status_code),
                        clean_text(note),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO finished_goods_stock (
                        finished_stock_id, product_id, production_batch_id, batch_number,
                        quantity_current, production_date, expiry_date
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        finished_stock_id,
                        product_id_value,
                        production_batch_id,
                        batch_number,
                        produced_qty - defective_qty,
                        production_dt.date(),
                        expiry_dt,
                    ),
                )
        set_flash(request, "Production batch and finished stock record created successfully.")
        return redirect_to("/production")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": "Add Production Batch", "action": "/production/new", "fields": production_fields(products, tech_cards, users, statuses, form_data), "back_url": "/production", "submit_label": "Create Production Batch", "error_message": str(exc)}, status_code=400)


@router.get("/finished-stock")
def finished_stock(request: Request):
    user = authorize_section(request, "finished_stock")
    if not isinstance(user, dict):
        return user
    today = date.today()
    rows = fetch_all(
        """
        SELECT
            fgs.finished_stock_id,
            p.name AS product_name,
            fgs.batch_number,
            fgs.quantity_current,
            p.unit,
            fgs.production_date,
            fgs.expiry_date
        FROM finished_goods_stock AS fgs
        JOIN products AS p ON p.product_id = fgs.product_id
        ORDER BY fgs.expiry_date, p.name
        """
    )
    for row in rows:
        if row["expiry_date"] < today:
            row["_row_class"] = "table-danger"
    return render_template(
        request,
        "table_list.html",
        {
            "title": "Finished Goods Stock",
            "subtitle": "Finished goods by batch with expiry control.",
            "headers": [
                ("finished_stock_id", "ID"),
                ("product_name", "Product"),
                ("batch_number", "Batch"),
                ("quantity_current", "Quantity"),
                ("unit", "Unit"),
                ("production_date", "Production Date"),
                ("expiry_date", "Expiry Date"),
            ],
            "rows": rows,
        },
    )
