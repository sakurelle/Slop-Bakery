from datetime import date, timedelta

from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_action, authorize_section, forbidden_response, redirect_to, render_template, set_flash
from ..database import fetch_all, fetch_one, get_db, next_id
from ..permissions import has_action
from ..utils import build_options, clean_text, parse_bool, parse_date, parse_decimal, parse_int


router = APIRouter()

DELIVERY_STOCK_STATUSES = {"received", "accepted"}
DELIVERY_MUTABLE_STATUSES = {"planned"}
DELIVERY_STATUS_TRANSITIONS = {
    "planned": {"received", "cancelled"},
    "received": {"accepted", "rejected"},
    "accepted": set(),
    "rejected": set(),
    "cancelled": set(),
}


def material_fields(data=None):
    data = data or {}
    return [
        {"name": "name", "label": "ÐÐ°Ð¸Ð¼ÐµÐ½Ð¾Ð²Ð°Ð½Ð¸Ðµ ÑÑ‹Ñ€ÑŒÑ", "type": "text", "required": True, "value": data.get("name", "")},
        {"name": "unit", "label": "Ð•Ð´Ð¸Ð½Ð¸Ñ†Ð° Ð¸Ð·Ð¼ÐµÑ€ÐµÐ½Ð¸Ñ", "type": "text", "required": True, "value": data.get("unit", "kg")},
        {"name": "min_stock_qty", "label": "ÐœÐ¸Ð½Ð¸Ð¼Ð°Ð»ÑŒÐ½Ñ‹Ð¹ Ð¾ÑÑ‚Ð°Ñ‚Ð¾Ðº", "type": "number", "required": True, "step": "0.001", "min": "0", "value": data.get("min_stock_qty", "0")},
        {"name": "shelf_life_days", "label": "Ð¡Ñ€Ð¾Ðº Ð³Ð¾Ð´Ð½Ð¾ÑÑ‚Ð¸ (Ð´Ð½ÐµÐ¹)", "type": "number", "min": "1", "value": data.get("shelf_life_days", "")},
        {"name": "storage_conditions", "label": "Ð£ÑÐ»Ð¾Ð²Ð¸Ñ Ñ…Ñ€Ð°Ð½ÐµÐ½Ð¸Ñ", "type": "textarea", "value": data.get("storage_conditions", "")},
        {"name": "is_active", "label": "ÐÐºÑ‚Ð¸Ð²Ð½Ð¾", "type": "checkbox", "value": bool(data.get("is_active", True))},
    ]


def delivery_fields(suppliers, data=None):
    data = data or {}
    return [
        {
            "name": "supplier_id",
            "label": "ÐŸÐ¾ÑÑ‚Ð°Ð²Ñ‰Ð¸Ðº",
            "type": "select",
            "required": True,
            "value": data.get("supplier_id", ""),
            "options": build_options(suppliers, "supplier_id", "company_name"),
        },
        {"name": "delivery_date", "label": "Ð”Ð°Ñ‚Ð° Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÐ¸", "type": "date", "required": True, "value": data.get("delivery_date", date.today().isoformat())},
        {"name": "document_ref", "label": "Ð”Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚", "type": "text", "value": data.get("document_ref", "")},
        {"name": "note", "label": "ÐŸÑ€Ð¸Ð¼ÐµÑ‡Ð°Ð½Ð¸Ðµ", "type": "textarea", "value": data.get("note", "")},
    ]


def delivery_item_fields(materials, data=None):
    data = data or {}
    return [
        {
            "name": "material_id",
            "label": "Сырьё",
            "type": "select",
            "required": True,
            "value": data.get("material_id", ""),
            "options": build_options(materials, "material_id", "name"),
        },
        {"name": "quantity", "label": "Количество", "type": "number", "required": True, "step": "0.001", "min": "0.001", "value": data.get("quantity", "")},
        {"name": "batch_number", "label": "Номер партии", "type": "text", "value": data.get("batch_number", "")},
        {"name": "expiry_date", "label": "Срок годности", "type": "date", "required": True, "value": data.get("expiry_date", "")},
    ]

def delivery_status_fields(statuses, current_status):
    return [
        {
            "name": "status_code",
            "label": "Ð¡Ñ‚Ð°Ñ‚ÑƒÑ",
            "type": "select",
            "required": True,
            "value": current_status,
            "options": build_options(statuses, "status_code", "name"),
        }
    ]


def fetch_delivery_for_user(delivery_id: int):
    return fetch_one(
        """
        SELECT d.*, s.company_name
        FROM raw_material_deliveries AS d
        JOIN suppliers AS s ON s.supplier_id = d.supplier_id
        WHERE d.delivery_id = %s
        """,
        (delivery_id,),
    )


def get_delivery_status_options(delivery: dict):
    next_statuses = sorted(DELIVERY_STATUS_TRANSITIONS.get(delivery["status_code"], set()))
    if not next_statuses:
        return []
    return fetch_all(
        """
        SELECT status_code, name
        FROM delivery_statuses
        WHERE status_code = ANY(%s)
        ORDER BY name
        """,
        (next_statuses,),
    )


def validate_delivery_status_change(delivery: dict, new_status: str):
    if new_status not in DELIVERY_STATUS_TRANSITIONS.get(delivery["status_code"], set()):
        raise ValueError("ÐÐµÐ´Ð¾Ð¿ÑƒÑÑ‚Ð¸Ð¼Ñ‹Ð¹ Ð¿ÐµÑ€ÐµÑ…Ð¾Ð´ ÑÑ‚Ð°Ñ‚ÑƒÑÐ° Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÐ¸.")


def sync_delivery_stock(conn, delivery_id: int) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT status_code FROM raw_material_deliveries WHERE delivery_id = %s", (delivery_id,))
        delivery = cur.fetchone()
        if not delivery:
            raise ValueError("ÐŸÐ¾ÑÑ‚Ð°Ð²ÐºÐ° Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð°.")
        if delivery["status_code"] not in DELIVERY_STOCK_STATUSES:
            raise ValueError("ÐžÑÑ‚Ð°Ñ‚Ð¾Ðº ÑÑ‹Ñ€ÑŒÑ Ð¼Ð¾Ð¶Ð½Ð¾ Ñ„Ð¾Ñ€Ð¼Ð¸Ñ€Ð¾Ð²Ð°Ñ‚ÑŒ Ñ‚Ð¾Ð»ÑŒÐºÐ¾ Ð´Ð»Ñ Ð¿Ð¾Ð»ÑƒÑ‡ÐµÐ½Ð½Ð¾Ð¹ Ð¸Ð»Ð¸ Ð¿Ñ€Ð¸Ð½ÑÑ‚Ð¾Ð¹ Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÐ¸.")

        cur.execute("SELECT COUNT(*) AS items_count FROM delivery_items WHERE delivery_id = %s", (delivery_id,))
        items_row = cur.fetchone()
        if not items_row or items_row["items_count"] <= 0:
            raise ValueError("ÐÐµÐ»ÑŒÐ·Ñ Ð¿Ñ€Ð¸Ð½ÑÑ‚ÑŒ Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÑƒ Ð±ÐµÐ· Ð¿Ð¾Ð·Ð¸Ñ†Ð¸Ð¹.")

        cur.execute(
            """
            SELECT di.delivery_item_id, di.material_id, di.batch_number, di.quantity, di.expiry_date
            FROM delivery_items AS di
            LEFT JOIN raw_material_stock AS rms ON rms.delivery_item_id = di.delivery_item_id
            WHERE di.delivery_id = %s
              AND rms.stock_id IS NULL
            ORDER BY di.delivery_item_id
            """,
            (delivery_id,),
        )
        missing_stock_items = cur.fetchall()

        created_count = 0
        for item in missing_stock_items:
            stock_id = next_id(conn, "raw_material_stock", "stock_id")
            cur.execute(
                """
                INSERT INTO raw_material_stock (
                    stock_id, material_id, delivery_item_id, batch_number, quantity_current, expiry_date
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    stock_id,
                    item["material_id"],
                    item["delivery_item_id"],
                    item["batch_number"],
                    item["quantity"],
                    item["expiry_date"],
                ),
            )
            created_count += 1
        return created_count


def validate_supplier_material(conn, supplier_id: int, material_id: int):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT purchase_price
            FROM supplier_materials
            WHERE supplier_id = %s
              AND material_id = %s
              AND is_active = TRUE
            LIMIT 1
            """,
            (supplier_id, material_id),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("Сырьё не закреплено за поставщиком.")
        if row["purchase_price"] is None:
            raise ValueError("Для этого поставщика не задана закупочная цена по выбранному сырью.")
        return row["purchase_price"]


def recalculate_delivery_total(conn, delivery_id: int):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE raw_material_deliveries
            SET total_amount = COALESCE((
                SELECT SUM(quantity * unit_price)
                FROM delivery_items
                WHERE delivery_id = %s
            ), 0)
            WHERE delivery_id = %s
            """,
            (delivery_id, delivery_id),
        )


def fetch_supplier_invoice_by_delivery(delivery_id: int):
    return fetch_one(
        """
        SELECT
            supplier_invoice_id,
            supplier_invoice_number,
            issue_date,
            due_date,
            amount,
            status_code,
            paid_at
        FROM supplier_invoices
        WHERE delivery_id = %s
        """,
        (delivery_id,),
    )


def create_supplier_invoice_for_delivery(conn, delivery_id: int) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT delivery_id, supplier_id, delivery_number, status_code, document_ref
            FROM raw_material_deliveries
            WHERE delivery_id = %s
            """,
            (delivery_id,),
        )
        delivery = cur.fetchone()
        if not delivery:
            raise ValueError("Поставка не найдена.")
        if delivery["status_code"] in {"rejected", "cancelled"}:
            raise ValueError("Нельзя создать счёт для отклонённой поставки.")
        if delivery["status_code"] != "accepted":
            raise ValueError("Счёт поставщика создаётся только после принятия поставки.")

        cur.execute(
            """
            SELECT supplier_invoice_id
            FROM supplier_invoices
            WHERE delivery_id = %s
            LIMIT 1
            """,
            (delivery_id,),
        )
        if cur.fetchone():
            return None

        cur.execute(
            """
            SELECT COUNT(*) AS items_count, COALESCE(SUM(quantity * unit_price), 0) AS total_amount
            FROM delivery_items
            WHERE delivery_id = %s
            """,
            (delivery_id,),
        )
        totals = cur.fetchone()
        if not totals or totals["items_count"] <= 0:
            raise ValueError("Нельзя создать счёт для поставки без позиций.")
        if totals["total_amount"] <= 0:
            raise ValueError("Нельзя создать счёт для поставки без позиций.")

    recalculate_delivery_total(conn, delivery_id)
    supplier_invoice_id = next_id(conn, "supplier_invoices", "supplier_invoice_id")
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO supplier_invoices (
                supplier_invoice_id,
                supplier_invoice_number,
                delivery_id,
                supplier_id,
                issue_date,
                due_date,
                paid_at,
                amount,
                status_code,
                document_ref,
                note
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                CURRENT_DATE,
                CURRENT_DATE + 7,
                NULL,
                %s,
                'issued',
                %s,
                %s
            )
            """,
            (
                supplier_invoice_id,
                f"SINV-WEB-{supplier_invoice_id:04d}",
                delivery_id,
                delivery["supplier_id"],
                totals["total_amount"],
                clean_text(delivery["document_ref"]),
                f"Счёт создан автоматически по поставке {delivery['delivery_number']}.",
            ),
        )
    return supplier_invoice_id

@router.get("/materials")
def materials_list(request: Request):
    user = authorize_section(request, "materials")
    if not isinstance(user, dict):
        return user
    rows = fetch_all(
        """
        SELECT
            rm.material_id,
            rm.name,
            rm.unit,
            rm.min_stock_qty,
            COALESCE(SUM(rms.quantity_current), 0) AS quantity_on_hand,
            rm.shelf_life_days,
            rm.is_active
        FROM raw_materials AS rm
        LEFT JOIN raw_material_stock AS rms ON rms.material_id = rm.material_id
        GROUP BY rm.material_id, rm.name, rm.unit, rm.min_stock_qty, rm.shelf_life_days, rm.is_active
        ORDER BY rm.material_id
        """
    )
    for row in rows:
        row["_detail_url"] = f"/materials/{row['material_id']}"
        if row["quantity_on_hand"] < row["min_stock_qty"]:
            row["_row_class"] = "table-danger"
    context = {
        "title": "Ð¡Ñ‹Ñ€ÑŒÑ‘",
        "subtitle": "Ð¡Ð¿Ñ€Ð°Ð²Ð¾Ñ‡Ð½Ð¸Ðº ÑÑ‹Ñ€ÑŒÑ Ñ Ð¾Ñ‚Ð¾Ð±Ñ€Ð°Ð¶ÐµÐ½Ð¸ÐµÐ¼ Ñ‚ÐµÐºÑƒÑ‰Ð¸Ñ… Ð¾ÑÑ‚Ð°Ñ‚ÐºÐ¾Ð².",
        "headers": [
            ("material_id", "ID"),
            ("name", "Ð¡Ñ‹Ñ€ÑŒÑ‘"),
            ("unit", "Ð•Ð´."),
            ("min_stock_qty", "ÐœÐ¸Ð½. Ð¾ÑÑ‚Ð°Ñ‚Ð¾Ðº"),
            ("quantity_on_hand", "Ð¢ÐµÐºÑƒÑ‰Ð¸Ð¹ Ð¾ÑÑ‚Ð°Ñ‚Ð¾Ðº"),
            ("shelf_life_days", "Ð¡Ñ€Ð¾Ðº Ð³Ð¾Ð´Ð½Ð¾ÑÑ‚Ð¸"),
            ("is_active", "ÐÐºÑ‚Ð¸Ð²Ð½Ð¾"),
        ],
        "rows": rows,
    }
    if has_action(user, "materials.manage"):
        context["create_url"] = "/materials/new"
        context["create_label"] = "Ð”Ð¾Ð±Ð°Ð²Ð¸Ñ‚ÑŒ ÑÑ‹Ñ€ÑŒÑ‘"
    return render_template(request, "table_list.html", context)


@router.get("/materials/new")
def material_new_page(request: Request):
    user = authorize_action(request, "materials.manage", "Ð£ Ð²Ð°Ñ Ð½ÐµÑ‚ Ð¿Ñ€Ð°Ð² Ð½Ð° ÑƒÐ¿Ñ€Ð°Ð²Ð»ÐµÐ½Ð¸Ðµ ÑÑ‹Ñ€ÑŒÑ‘Ð¼.")
    if not isinstance(user, dict):
        return user
    return render_template(request, "form.html", {"title": "Ð”Ð¾Ð±Ð°Ð²Ð¸Ñ‚ÑŒ ÑÑ‹Ñ€ÑŒÑ‘", "action": "/materials/new", "fields": material_fields(), "back_url": "/materials", "submit_label": "Ð¡Ð¾Ð·Ð´Ð°Ñ‚ÑŒ Ð·Ð°Ð¿Ð¸ÑÑŒ"})


@router.post("/materials/new")
def material_new(
    request: Request,
    name: str = Form(...),
    unit: str = Form(...),
    min_stock_qty: str = Form(...),
    shelf_life_days: str = Form(""),
    storage_conditions: str = Form(""),
    is_active: str | None = Form(None),
):
    user = authorize_action(request, "materials.manage", "Ð£ Ð²Ð°Ñ Ð½ÐµÑ‚ Ð¿Ñ€Ð°Ð² Ð½Ð° ÑƒÐ¿Ñ€Ð°Ð²Ð»ÐµÐ½Ð¸Ðµ ÑÑ‹Ñ€ÑŒÑ‘Ð¼.")
    if not isinstance(user, dict):
        return user
    form_data = {"name": name, "unit": unit, "min_stock_qty": min_stock_qty, "shelf_life_days": shelf_life_days, "storage_conditions": storage_conditions, "is_active": parse_bool(is_active)}
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            material_id = next_id(conn, "raw_materials", "material_id")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO raw_materials (
                        material_id, name, unit, min_stock_qty, shelf_life_days, storage_conditions, is_active
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        material_id,
                        clean_text(name),
                        clean_text(unit),
                        parse_decimal(min_stock_qty, "ÐœÐ¸Ð½Ð¸Ð¼Ð°Ð»ÑŒÐ½Ñ‹Ð¹ Ð¾ÑÑ‚Ð°Ñ‚Ð¾Ðº"),
                        parse_int(shelf_life_days, "Ð¡Ñ€Ð¾Ðº Ð³Ð¾Ð´Ð½Ð¾ÑÑ‚Ð¸", allow_none=True),
                        clean_text(storage_conditions),
                        parse_bool(is_active),
                    ),
                )
        set_flash(request, "Ð¡Ñ‹Ñ€ÑŒÑ‘ ÑƒÑÐ¿ÐµÑˆÐ½Ð¾ Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ð¾.")
        return redirect_to("/materials")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "ÐÐµ ÑƒÐ´Ð°Ð»Ð¾ÑÑŒ Ð´Ð¾Ð±Ð°Ð²Ð¸Ñ‚ÑŒ ÑÑ‹Ñ€ÑŒÑ‘."
    return render_template(request, "form.html", {"title": "Ð”Ð¾Ð±Ð°Ð²Ð¸Ñ‚ÑŒ ÑÑ‹Ñ€ÑŒÑ‘", "action": "/materials/new", "fields": material_fields(form_data), "back_url": "/materials", "submit_label": "Ð¡Ð¾Ð·Ð´Ð°Ñ‚ÑŒ Ð·Ð°Ð¿Ð¸ÑÑŒ", "error_message": error_message}, status_code=400)


@router.get("/materials/{material_id}")
def material_detail(request: Request, material_id: int):
    user = authorize_section(request, "materials")
    if not isinstance(user, dict):
        return user
    material = fetch_one("SELECT * FROM raw_materials WHERE material_id = %s", (material_id,))
    if not material:
        return render_template(request, "error.html", {"title": "Ð¡Ñ‹Ñ€ÑŒÑ‘ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð¾", "message": "ÐšÐ°Ñ€Ñ‚Ð¾Ñ‡ÐºÐ° ÑÑ‹Ñ€ÑŒÑ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð°."}, status_code=404)
    stock_rows = fetch_all(
        """
        SELECT batch_number, quantity_current, expiry_date, updated_at
        FROM raw_material_stock
        WHERE material_id = %s
        ORDER BY expiry_date
        """,
        (material_id,),
    )
    return render_template(
        request,
        "detail.html",
        {
            "title": material["name"],
            "back_url": "/materials",
            "edit_url": f"/materials/{material_id}/edit" if has_action(user, "materials.manage") else None,
            "details": [
                ("ID", material["material_id"]),
                ("Ð•Ð´Ð¸Ð½Ð¸Ñ†Ð° Ð¸Ð·Ð¼ÐµÑ€ÐµÐ½Ð¸Ñ", material["unit"]),
                ("ÐœÐ¸Ð½Ð¸Ð¼Ð°Ð»ÑŒÐ½Ñ‹Ð¹ Ð¾ÑÑ‚Ð°Ñ‚Ð¾Ðº", material["min_stock_qty"]),
                ("Ð¡Ñ€Ð¾Ðº Ð³Ð¾Ð´Ð½Ð¾ÑÑ‚Ð¸, Ð´Ð½ÐµÐ¹", material["shelf_life_days"]),
                ("Ð£ÑÐ»Ð¾Ð²Ð¸Ñ Ñ…Ñ€Ð°Ð½ÐµÐ½Ð¸Ñ", material["storage_conditions"]),
                ("ÐÐºÑ‚Ð¸Ð²Ð½Ð¾", material["is_active"]),
            ],
            "sections": [
                {
                    "title": "ÐŸÐ°Ñ€Ñ‚Ð¸Ð¸ Ð½Ð° ÑÐºÐ»Ð°Ð´Ðµ",
                    "headers": [("batch_number", "ÐŸÐ°Ñ€Ñ‚Ð¸Ñ"), ("quantity_current", "ÐšÐ¾Ð»Ð¸Ñ‡ÐµÑÑ‚Ð²Ð¾"), ("expiry_date", "Ð¡Ñ€Ð¾Ðº Ð³Ð¾Ð´Ð½Ð¾ÑÑ‚Ð¸"), ("updated_at", "ÐžÐ±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¾")],
                    "rows": stock_rows,
                    "empty_message": "Ð”Ð»Ñ ÑÑ‚Ð¾Ð³Ð¾ ÑÑ‹Ñ€ÑŒÑ ÑÐºÐ»Ð°Ð´ÑÐºÐ¸Ñ… Ð¿Ð°Ñ€Ñ‚Ð¸Ð¹ Ð½ÐµÑ‚.",
                }
            ],
        },
    )


@router.get("/materials/{material_id}/edit")
def material_edit_page(request: Request, material_id: int):
    user = authorize_action(request, "materials.manage", "Ð£ Ð²Ð°Ñ Ð½ÐµÑ‚ Ð¿Ñ€Ð°Ð² Ð½Ð° ÑƒÐ¿Ñ€Ð°Ð²Ð»ÐµÐ½Ð¸Ðµ ÑÑ‹Ñ€ÑŒÑ‘Ð¼.")
    if not isinstance(user, dict):
        return user
    material = fetch_one("SELECT * FROM raw_materials WHERE material_id = %s", (material_id,))
    if not material:
        return render_template(request, "error.html", {"title": "Ð¡Ñ‹Ñ€ÑŒÑ‘ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð¾", "message": "ÐšÐ°Ñ€Ñ‚Ð¾Ñ‡ÐºÐ° ÑÑ‹Ñ€ÑŒÑ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð°."}, status_code=404)
    return render_template(request, "form.html", {"title": f"Ð ÐµÐ´Ð°ÐºÑ‚Ð¸Ñ€Ð¾Ð²Ð°Ñ‚ÑŒ ÑÑ‹Ñ€ÑŒÑ‘ #{material_id}", "action": f"/materials/{material_id}/edit", "fields": material_fields(material), "back_url": f"/materials/{material_id}", "submit_label": "Ð¡Ð¾Ñ…Ñ€Ð°Ð½Ð¸Ñ‚ÑŒ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ñ"})


@router.post("/materials/{material_id}/edit")
def material_edit(
    request: Request,
    material_id: int,
    name: str = Form(...),
    unit: str = Form(...),
    min_stock_qty: str = Form(...),
    shelf_life_days: str = Form(""),
    storage_conditions: str = Form(""),
    is_active: str | None = Form(None),
):
    user = authorize_action(request, "materials.manage", "Ð£ Ð²Ð°Ñ Ð½ÐµÑ‚ Ð¿Ñ€Ð°Ð² Ð½Ð° ÑƒÐ¿Ñ€Ð°Ð²Ð»ÐµÐ½Ð¸Ðµ ÑÑ‹Ñ€ÑŒÑ‘Ð¼.")
    if not isinstance(user, dict):
        return user
    form_data = {"name": name, "unit": unit, "min_stock_qty": min_stock_qty, "shelf_life_days": shelf_life_days, "storage_conditions": storage_conditions, "is_active": parse_bool(is_active)}
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE raw_materials
                    SET name = %s,
                        unit = %s,
                        min_stock_qty = %s,
                        shelf_life_days = %s,
                        storage_conditions = %s,
                        is_active = %s
                    WHERE material_id = %s
                    """,
                    (
                        clean_text(name),
                        clean_text(unit),
                        parse_decimal(min_stock_qty, "ÐœÐ¸Ð½Ð¸Ð¼Ð°Ð»ÑŒÐ½Ñ‹Ð¹ Ð¾ÑÑ‚Ð°Ñ‚Ð¾Ðº"),
                        parse_int(shelf_life_days, "Ð¡Ñ€Ð¾Ðº Ð³Ð¾Ð´Ð½Ð¾ÑÑ‚Ð¸", allow_none=True),
                        clean_text(storage_conditions),
                        parse_bool(is_active),
                        material_id,
                    ),
                )
        set_flash(request, "Ð”Ð°Ð½Ð½Ñ‹Ðµ Ð¿Ð¾ ÑÑ‹Ñ€ÑŒÑŽ ÑƒÑÐ¿ÐµÑˆÐ½Ð¾ Ð¾Ð±Ð½Ð¾Ð²Ð»ÐµÐ½Ñ‹.")
        return redirect_to(f"/materials/{material_id}")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "ÐÐµ ÑƒÐ´Ð°Ð»Ð¾ÑÑŒ Ð¾Ð±Ð½Ð¾Ð²Ð¸Ñ‚ÑŒ Ð´Ð°Ð½Ð½Ñ‹Ðµ Ð¿Ð¾ ÑÑ‹Ñ€ÑŒÑŽ."
    return render_template(request, "form.html", {"title": f"Ð ÐµÐ´Ð°ÐºÑ‚Ð¸Ñ€Ð¾Ð²Ð°Ñ‚ÑŒ ÑÑ‹Ñ€ÑŒÑ‘ #{material_id}", "action": f"/materials/{material_id}/edit", "fields": material_fields(form_data), "back_url": f"/materials/{material_id}", "submit_label": "Ð¡Ð¾Ñ…Ñ€Ð°Ð½Ð¸Ñ‚ÑŒ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ñ", "error_message": error_message}, status_code=400)


@router.get("/deliveries")
def deliveries_list(request: Request):
    user = authorize_section(request, "deliveries")
    if not isinstance(user, dict):
        return user
    rows = fetch_all(
        """
        SELECT
            d.delivery_id,
            d.delivery_number,
            s.company_name,
            d.delivery_date,
            d.status_code,
            d.total_amount
        FROM raw_material_deliveries AS d
        JOIN suppliers AS s ON s.supplier_id = d.supplier_id
        ORDER BY d.delivery_date DESC, d.delivery_id DESC
        """
    )
    for row in rows:
        row["_detail_url"] = f"/deliveries/{row['delivery_id']}"
    context = {
        "title": "ÐŸÐ¾ÑÑ‚Ð°Ð²ÐºÐ¸ ÑÑ‹Ñ€ÑŒÑ",
        "subtitle": "Ð’Ñ…Ð¾Ð´ÑÑ‰Ð¸Ðµ Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÐ¸ Ð¾Ñ‚ Ð¿Ð¾ÑÑ‚Ð°Ð²Ñ‰Ð¸ÐºÐ¾Ð².",
        "headers": [
            ("delivery_id", "ID"),
            ("delivery_number", "ÐÐ¾Ð¼ÐµÑ€ Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÐ¸"),
            ("company_name", "ÐŸÐ¾ÑÑ‚Ð°Ð²Ñ‰Ð¸Ðº"),
            ("delivery_date", "Ð”Ð°Ñ‚Ð°"),
            ("status_code", "Ð¡Ñ‚Ð°Ñ‚ÑƒÑ"),
            ("total_amount", "Ð¡ÑƒÐ¼Ð¼Ð°"),
        ],
        "rows": rows,
    }
    if has_action(user, "deliveries.create"):
        context["create_url"] = "/deliveries/new"
        context["create_label"] = "Ð¡Ð¾Ð·Ð´Ð°Ñ‚ÑŒ Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÑƒ"
    return render_template(request, "table_list.html", context)


@router.get("/deliveries/new")
def delivery_new_page(request: Request):
    user = authorize_action(request, "deliveries.create", "Ð£ Ð²Ð°Ñ Ð½ÐµÑ‚ Ð¿Ñ€Ð°Ð² Ð½Ð° ÑÐ¾Ð·Ð´Ð°Ð½Ð¸Ðµ Ð¿Ð¾ÑÑ‚Ð°Ð²Ð¾Ðº.")
    if not isinstance(user, dict):
        return user
    suppliers = fetch_all("SELECT supplier_id, company_name FROM suppliers WHERE is_active = TRUE ORDER BY company_name")
    return render_template(request, "form.html", {"title": "Ð¡Ð¾Ð·Ð´Ð°Ñ‚ÑŒ Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÑƒ", "action": "/deliveries/new", "fields": delivery_fields(suppliers), "back_url": "/deliveries", "submit_label": "Ð¡Ð¾Ð·Ð´Ð°Ñ‚ÑŒ Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÑƒ"})


@router.post("/deliveries/new")
def delivery_new(
    request: Request,
    supplier_id: str = Form(...),
    delivery_date: str = Form(...),
    document_ref: str = Form(""),
    note: str = Form(""),
):
    user = authorize_action(request, "deliveries.create", "Ð£ Ð²Ð°Ñ Ð½ÐµÑ‚ Ð¿Ñ€Ð°Ð² Ð½Ð° ÑÐ¾Ð·Ð´Ð°Ð½Ð¸Ðµ Ð¿Ð¾ÑÑ‚Ð°Ð²Ð¾Ðº.")
    if not isinstance(user, dict):
        return user
    suppliers = fetch_all("SELECT supplier_id, company_name FROM suppliers WHERE is_active = TRUE ORDER BY company_name")
    form_data = {"supplier_id": supplier_id, "delivery_date": delivery_date, "document_ref": document_ref, "note": note}
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            delivery_id = next_id(conn, "raw_material_deliveries", "delivery_id")
            delivery_number = f"DN-WEB-{delivery_id:04d}"
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO raw_material_deliveries (
                        delivery_id, supplier_id, delivery_number, delivery_date, status_code,
                        received_by_user_id, document_ref, total_amount, note
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        delivery_id,
                        parse_int(supplier_id, "ÐŸÐ¾ÑÑ‚Ð°Ð²Ñ‰Ð¸Ðº"),
                        delivery_number,
                        parse_date(delivery_date, "Ð”Ð°Ñ‚Ð° Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÐ¸"),
                        "planned",
                        user["user_id"],
                        clean_text(document_ref),
                        0,
                        clean_text(note),
                    ),
                )
        set_flash(request, "ÐŸÐ¾ÑÑ‚Ð°Ð²ÐºÐ° ÑÐ¾Ð·Ð´Ð°Ð½Ð° ÑÐ¾ ÑÑ‚Ð°Ñ‚ÑƒÑÐ¾Ð¼ Â«Ð—Ð°Ð¿Ð»Ð°Ð½Ð¸Ñ€Ð¾Ð²Ð°Ð½Ð°Â». Ð¢ÐµÐ¿ÐµÑ€ÑŒ Ð¼Ð¾Ð¶Ð½Ð¾ Ð´Ð¾Ð±Ð°Ð²Ð¸Ñ‚ÑŒ ÐµÑ‘ Ð¿Ð¾Ð·Ð¸Ñ†Ð¸Ð¸.")
        return redirect_to(f"/deliveries/{delivery_id}")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "ÐÐµ ÑƒÐ´Ð°Ð»Ð¾ÑÑŒ ÑÐ¾Ð·Ð´Ð°Ñ‚ÑŒ Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÑƒ."
    return render_template(request, "form.html", {"title": "Ð¡Ð¾Ð·Ð´Ð°Ñ‚ÑŒ Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÑƒ", "action": "/deliveries/new", "fields": delivery_fields(suppliers, form_data), "back_url": "/deliveries", "submit_label": "Ð¡Ð¾Ð·Ð´Ð°Ñ‚ÑŒ Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÑƒ", "error_message": error_message}, status_code=400)


@router.get("/deliveries/{delivery_id}")
def delivery_detail(request: Request, delivery_id: int):
    user = authorize_section(request, "deliveries")
    if not isinstance(user, dict):
        return user
    delivery = fetch_delivery_for_user(delivery_id)
    if not delivery:
        return render_template(request, "error.html", {"title": "Поставка не найдена", "message": "Карточка поставки не найдена."}, status_code=404)
    items = fetch_all(
        """
        SELECT di.delivery_item_id, rm.name, di.quantity, di.unit_price, di.batch_number, di.expiry_date
        FROM delivery_items AS di
        JOIN raw_materials AS rm ON rm.material_id = di.material_id
        WHERE di.delivery_id = %s
        ORDER BY di.delivery_item_id
        """,
        (delivery_id,),
    )
    supplier_invoice = fetch_supplier_invoice_by_delivery(delivery_id)
    extra_actions = []
    if has_action(user, "deliveries.add_item") and delivery["status_code"] in DELIVERY_MUTABLE_STATUSES:
        extra_actions.append({"label": "Добавить позицию", "url": f"/deliveries/{delivery_id}/items/new"})
    if has_action(user, "deliveries.change_status") and get_delivery_status_options(delivery):
        extra_actions.append({"label": "Изменить статус", "url": f"/deliveries/{delivery_id}/status"})

    invoice_rows = []
    invoice_empty_message = "Счёт поставщика отсутствует."
    if supplier_invoice:
        supplier_invoice["_detail_url"] = f"/supplier-invoices/{supplier_invoice['supplier_invoice_id']}"
        if has_action(user, "supplier_invoices.pay") and supplier_invoice["status_code"] in {"issued", "overdue"}:
            supplier_invoice["_row_forms"] = [
                {
                    "action": f"/supplier-invoices/{supplier_invoice['supplier_invoice_id']}/pay",
                    "label": "Оплатить",
                    "class": "btn-outline-success",
                }
            ]
        invoice_rows = [supplier_invoice]
    elif delivery["status_code"] in {"planned", "received"}:
        invoice_empty_message = "Счёт будет создан после принятия поставки."
    elif delivery["status_code"] in {"rejected", "cancelled"}:
        invoice_empty_message = "Счёт не создаётся для отклонённой или отменённой поставки."

    return render_template(
        request,
        "detail.html",
        {
            "title": delivery["delivery_number"],
            "back_url": "/deliveries",
            "extra_actions": extra_actions,
            "details": [
                ("ID", delivery["delivery_id"]),
                ("Поставщик", delivery["company_name"]),
                ("Дата поставки", delivery["delivery_date"]),
                ("Статус", delivery["status_code"]),
                ("Документ", delivery["document_ref"]),
                ("Общая сумма", delivery["total_amount"]),
                ("Примечание", delivery["note"]),
            ],
            "sections": [
                {
                    "title": "Позиции поставки",
                    "headers": [("delivery_item_id", "ID"), ("name", "Сырьё"), ("quantity", "Количество"), ("unit_price", "Цена за ед."), ("batch_number", "Партия"), ("expiry_date", "Срок годности")],
                    "rows": items,
                    "empty_message": "Позиции поставки ещё не добавлены.",
                },
                {
                    "title": "Счёт поставщика",
                    "headers": [("supplier_invoice_number", "Номер счёта"), ("issue_date", "Дата выставления"), ("due_date", "Срок оплаты"), ("amount", "Сумма"), ("status_code", "Статус"), ("paid_at", "Дата оплаты")],
                    "rows": invoice_rows,
                    "empty_message": invoice_empty_message,
                },
            ],
        },
    )

@router.get("/deliveries/{delivery_id}/items/new")
def delivery_item_new_page(request: Request, delivery_id: int):
    user = authorize_action(request, "deliveries.add_item", "Ð£ Ð²Ð°Ñ Ð½ÐµÑ‚ Ð¿Ñ€Ð°Ð² Ð½Ð° Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ð¸Ðµ Ð¿Ð¾Ð·Ð¸Ñ†Ð¸Ð¹ Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÐ¸.")
    if not isinstance(user, dict):
        return user
    delivery = fetch_delivery_for_user(delivery_id)
    if not delivery:
        return render_template(request, "error.html", {"title": "ÐŸÐ¾ÑÑ‚Ð°Ð²ÐºÐ° Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð°", "message": "ÐšÐ°Ñ€Ñ‚Ð¾Ñ‡ÐºÐ° Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÐ¸ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð°."}, status_code=404)
    if delivery["status_code"] not in DELIVERY_MUTABLE_STATUSES:
        return forbidden_response(request, "ÐÐµÐ»ÑŒÐ·Ñ Ð´Ð¾Ð±Ð°Ð²Ð»ÑÑ‚ÑŒ Ð¿Ð¾Ð·Ð¸Ñ†Ð¸Ð¸ Ð² Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÑƒ Ñ ÑÑ‚Ð¸Ð¼ ÑÑ‚Ð°Ñ‚ÑƒÑÐ¾Ð¼.")
    materials = fetch_all("SELECT material_id, name FROM raw_materials WHERE is_active = TRUE ORDER BY name")
    return render_template(request, "form.html", {"title": f"Ð”Ð¾Ð±Ð°Ð²Ð¸Ñ‚ÑŒ Ð¿Ð¾Ð·Ð¸Ñ†Ð¸ÑŽ Ð² Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÑƒ #{delivery_id}", "action": f"/deliveries/{delivery_id}/items/new", "fields": delivery_item_fields(materials), "back_url": f"/deliveries/{delivery_id}", "submit_label": "Ð”Ð¾Ð±Ð°Ð²Ð¸Ñ‚ÑŒ Ð¿Ð¾Ð·Ð¸Ñ†Ð¸ÑŽ"})


@router.post("/deliveries/{delivery_id}/items/new")
def delivery_item_new(
    request: Request,
    delivery_id: int,
    material_id: str = Form(...),
    quantity: str = Form(...),
    batch_number: str = Form(""),
    expiry_date: str = Form(...),
):
    user = authorize_action(request, "deliveries.add_item", "У вас нет прав на добавление позиций поставки.")
    if not isinstance(user, dict):
        return user
    delivery = fetch_delivery_for_user(delivery_id)
    if not delivery:
        return render_template(request, "error.html", {"title": "Поставка не найдена", "message": "Карточка поставки не найдена."}, status_code=404)
    materials = fetch_material_options()
    form_data = {"material_id": material_id, "quantity": quantity, "batch_number": batch_number, "expiry_date": expiry_date}

    if delivery["status_code"] not in DELIVERY_MUTABLE_STATUSES:
        return forbidden_response(request, "Нельзя добавлять позиции в поставку с этим статусом.")

    try:
        material_id_value = parse_int(material_id, "Сырьё")
        quantity_value = parse_decimal(quantity, "Количество")
        expiry_date_value = parse_date(expiry_date, "Срок годности")
        batch_value = clean_text(batch_number)
        if quantity_value <= 0:
            raise ValueError("Количество должно быть больше нуля.")
        if expiry_date_value <= delivery["delivery_date"]:
            raise ValueError("Срок годности должен быть позже даты поставки.")

        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            unit_price_value = validate_supplier_material(conn, delivery["supplier_id"], material_id_value)
            delivery_item_id = next_id(conn, "delivery_items", "delivery_item_id")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO delivery_items (
                        delivery_item_id, delivery_id, material_id, quantity, unit_price, batch_number, expiry_date
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (delivery_item_id, delivery_id, material_id_value, quantity_value, unit_price_value, batch_value, expiry_date_value),
                )
            recalculate_delivery_total(conn, delivery_id)
        set_flash(request, "Позиция поставки успешно добавлена. Цена зафиксирована по данным поставщика.")
        return redirect_to(f"/deliveries/{delivery_id}")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "Не удалось сохранить позицию поставки."
    return render_template(request, "form.html", {"title": f"Добавить позицию в поставку #{delivery_id}", "action": f"/deliveries/{delivery_id}/items/new", "fields": delivery_item_fields(materials, form_data), "back_url": f"/deliveries/{delivery_id}", "submit_label": "Добавить позицию", "error_message": error_message}, status_code=400)

@router.get("/deliveries/{delivery_id}/status")
def delivery_status_page(request: Request, delivery_id: int):
    user = authorize_action(request, "deliveries.change_status", "Ð£ Ð²Ð°Ñ Ð½ÐµÑ‚ Ð¿Ñ€Ð°Ð² Ð½Ð° Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ðµ ÑÑ‚Ð°Ñ‚ÑƒÑÐ° Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÐ¸.")
    if not isinstance(user, dict):
        return user
    delivery = fetch_delivery_for_user(delivery_id)
    if not delivery:
        return render_template(request, "error.html", {"title": "ÐŸÐ¾ÑÑ‚Ð°Ð²ÐºÐ° Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð°", "message": "ÐšÐ°Ñ€Ñ‚Ð¾Ñ‡ÐºÐ° Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÐ¸ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð°."}, status_code=404)
    statuses = get_delivery_status_options(delivery)
    if not statuses:
        return forbidden_response(request, "Ð”Ð»Ñ Ñ‚ÐµÐºÑƒÑ‰ÐµÐ³Ð¾ ÑÑ‚Ð°Ñ‚ÑƒÑÐ° Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÐ¸ Ð½ÐµÑ‚ Ð´Ð¾Ð¿ÑƒÑÑ‚Ð¸Ð¼Ñ‹Ñ… Ð¿ÐµÑ€ÐµÑ…Ð¾Ð´Ð¾Ð².")
    return render_template(request, "form.html", {"title": f"Ð˜Ð·Ð¼ÐµÐ½Ð¸Ñ‚ÑŒ ÑÑ‚Ð°Ñ‚ÑƒÑ Ð¿Ð¾ÑÑ‚Ð°Ð²ÐºÐ¸ #{delivery_id}", "action": f"/deliveries/{delivery_id}/status", "fields": delivery_status_fields(statuses, statuses[0]['status_code']), "back_url": f"/deliveries/{delivery_id}", "submit_label": "ÐžÐ±Ð½Ð¾Ð²Ð¸Ñ‚ÑŒ ÑÑ‚Ð°Ñ‚ÑƒÑ"})


@router.post("/deliveries/{delivery_id}/status")
def delivery_status_update(request: Request, delivery_id: int, status_code: str = Form(...)):
    user = authorize_action(request, "deliveries.change_status", "У вас нет прав на изменение статуса поставки.")
    if not isinstance(user, dict):
        return user
    delivery = fetch_delivery_for_user(delivery_id)
    if not delivery:
        return render_template(request, "error.html", {"title": "Поставка не найдена", "message": "Карточка поставки не найдена."}, status_code=404)
    statuses = get_delivery_status_options(delivery)
    try:
        new_status = clean_text(status_code)
        if not new_status:
            raise ValueError("Не выбран новый статус поставки.")
        validate_delivery_status_change(delivery, new_status)

        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE raw_material_deliveries
                    SET status_code = %s,
                        received_by_user_id = CASE WHEN %s IN ('received', 'accepted') THEN %s ELSE received_by_user_id END
                    WHERE delivery_id = %s
                    """,
                    (new_status, new_status, user["user_id"], delivery_id),
                )

            created_count = 0
            created_invoice_id = None
            if new_status in DELIVERY_STOCK_STATUSES:
                created_count = sync_delivery_stock(conn, delivery_id)
            if new_status == "accepted":
                created_invoice_id = create_supplier_invoice_for_delivery(conn, delivery_id)

        messages = ["Статус поставки успешно обновлён."]
        if created_count:
            messages.append(f"На склад добавлено партий: {created_count}.")
        if created_invoice_id:
            messages.append(f"Счёт поставщика создан автоматически: SINV-WEB-{created_invoice_id:04d}.")
        set_flash(request, " ".join(messages))
        return redirect_to(f"/deliveries/{delivery_id}")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "Не удалось изменить статус поставки."
    return render_template(request, "form.html", {"title": f"Изменить статус поставки #{delivery_id}", "action": f"/deliveries/{delivery_id}/status", "fields": delivery_status_fields(statuses, clean_text(status_code) or delivery['status_code']), "back_url": f"/deliveries/{delivery_id}", "submit_label": "Обновить статус", "error_message": error_message}, status_code=400)

@router.get("/material-stock")
def material_stock(request: Request):
    user = authorize_section(request, "material_stock")
    if not isinstance(user, dict):
        return user
    today = date.today()
    soon_limit = today + timedelta(days=7)
    rows = fetch_all(
        """
        SELECT
            rms.stock_id,
            rm.name AS material_name,
            rms.batch_number,
            rms.quantity_current,
            rm.unit,
            rms.expiry_date,
            rms.updated_at
        FROM raw_material_stock AS rms
        JOIN raw_materials AS rm ON rm.material_id = rms.material_id
        ORDER BY rms.expiry_date, rm.name
        """
    )
    for row in rows:
        expiry = row["expiry_date"]
        if expiry < today:
            row["_row_class"] = "table-danger"
        elif expiry <= soon_limit:
            row["_row_class"] = "table-warning"
    return render_template(
        request,
        "table_list.html",
        {
            "title": "ÐžÑÑ‚Ð°Ñ‚ÐºÐ¸ ÑÑ‹Ñ€ÑŒÑ",
            "subtitle": "Ð¡ÐºÐ»Ð°Ð´ÑÐºÐ¸Ðµ Ð¾ÑÑ‚Ð°Ñ‚ÐºÐ¸ Ð¿Ð¾ Ð¿Ð°Ñ€Ñ‚Ð¸ÑÐ¼. ÐŸÑ€Ð¾ÑÑ€Ð¾Ñ‡ÐµÐ½Ð½Ñ‹Ðµ Ð¸ ÑÐºÐ¾Ñ€Ð¾ Ð¸ÑÑ‚ÐµÐºÐ°ÑŽÑ‰Ð¸Ðµ Ð¿Ð°Ñ€Ñ‚Ð¸Ð¸ Ð¿Ð¾Ð´ÑÐ²ÐµÑ‡ÐµÐ½Ñ‹.",
            "headers": [
                ("stock_id", "ID"),
                ("material_name", "Ð¡Ñ‹Ñ€ÑŒÑ‘"),
                ("batch_number", "ÐŸÐ°Ñ€Ñ‚Ð¸Ñ"),
                ("quantity_current", "ÐšÐ¾Ð»Ð¸Ñ‡ÐµÑÑ‚Ð²Ð¾"),
                ("unit", "Ð•Ð´."),
                ("expiry_date", "Ð¡Ñ€Ð¾Ðº Ð³Ð¾Ð´Ð½Ð¾ÑÑ‚Ð¸"),
                ("updated_at", "ÐžÐ±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¾"),
            ],
            "rows": rows,
        },
    )






