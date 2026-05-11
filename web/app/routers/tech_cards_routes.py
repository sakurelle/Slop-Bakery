from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_section, redirect_to, render_template, set_flash
from ..database import fetch_all, fetch_one, get_db, next_id
from ..utils import build_options, clean_text, parse_date, parse_decimal, parse_int


router = APIRouter()


def tech_card_fields(products, statuses, approvers, data=None):
    data = data or {}
    return [
        {
            "name": "product_id",
            "label": "Product",
            "type": "select",
            "required": True,
            "value": data.get("product_id", ""),
            "options": build_options(products, "product_id", "name"),
        },
        {"name": "card_number", "label": "Card Number", "type": "text", "required": True, "value": data.get("card_number", "")},
        {"name": "version", "label": "Version", "type": "number", "required": True, "min": "1", "value": data.get("version", "1")},
        {
            "name": "status_code",
            "label": "Status",
            "type": "select",
            "required": True,
            "value": data.get("status_code", "draft"),
            "options": build_options(statuses, "status_code", "name"),
        },
        {"name": "effective_from", "label": "Effective From", "type": "date", "required": True, "value": data.get("effective_from", "")},
        {"name": "effective_to", "label": "Effective To", "type": "date", "value": data.get("effective_to", "")},
        {"name": "baking_time_min", "label": "Baking Time (min)", "type": "number", "required": True, "min": "1", "value": data.get("baking_time_min", "")},
        {"name": "baking_temperature_c", "label": "Baking Temperature (C)", "type": "number", "required": True, "step": "0.01", "min": "0.01", "value": data.get("baking_temperature_c", "")},
        {"name": "process_description", "label": "Process Description", "type": "textarea", "required": True, "value": data.get("process_description", "")},
        {
            "name": "approved_by_user_id",
            "label": "Approved By",
            "type": "select",
            "value": data.get("approved_by_user_id", ""),
            "options": build_options(approvers, "user_id", "full_name", blank_label="Not approved yet"),
        },
    ]


def recipe_item_fields(materials, data=None):
    data = data or {}
    return [
        {
            "name": "material_id",
            "label": "Material",
            "type": "select",
            "required": True,
            "value": data.get("material_id", ""),
            "options": build_options(materials, "material_id", "name"),
        },
        {"name": "quantity", "label": "Quantity", "type": "number", "required": True, "step": "0.001", "min": "0.001", "value": data.get("quantity", "")},
        {"name": "unit", "label": "Unit", "type": "text", "required": True, "value": data.get("unit", "kg")},
        {"name": "stage", "label": "Stage", "type": "text", "value": data.get("stage", "")},
        {"name": "waste_percent", "label": "Waste Percent", "type": "number", "step": "0.01", "min": "0", "max": "99.99", "value": data.get("waste_percent", "0")},
        {"name": "note", "label": "Note", "type": "textarea", "value": data.get("note", "")},
    ]


@router.get("/tech-cards")
def tech_cards_list(request: Request):
    user = authorize_section(request, "tech_cards")
    if not isinstance(user, dict):
        return user
    rows = fetch_all(
        """
        SELECT
            tc.tech_card_id,
            tc.card_number,
            p.name AS product_name,
            tc.version,
            tc.status_code,
            tc.effective_from,
            tc.effective_to
        FROM tech_cards AS tc
        JOIN products AS p ON p.product_id = tc.product_id
        ORDER BY tc.tech_card_id
        """
    )
    for row in rows:
        row["_detail_url"] = f"/tech-cards/{row['tech_card_id']}"
    return render_template(
        request,
        "table_list.html",
        {
            "title": "Tech Cards",
            "subtitle": "Product technology cards and recipe compositions.",
            "headers": [
                ("tech_card_id", "ID"),
                ("card_number", "Card Number"),
                ("product_name", "Product"),
                ("version", "Version"),
                ("status_code", "Status"),
                ("effective_from", "Effective From"),
                ("effective_to", "Effective To"),
            ],
            "rows": rows,
            "create_url": "/tech-cards/new",
            "create_label": "Add Tech Card",
        },
    )


@router.get("/tech-cards/new")
def tech_card_new_page(request: Request):
    user = authorize_section(request, "tech_cards")
    if not isinstance(user, dict):
        return user
    products = fetch_all("SELECT product_id, name FROM products WHERE is_active = TRUE ORDER BY name")
    statuses = fetch_all("SELECT status_code, name FROM tech_card_statuses ORDER BY name")
    approvers = fetch_all("SELECT user_id, full_name FROM users WHERE status_code = 'active' ORDER BY full_name")
    return render_template(request, "form.html", {"title": "Add Tech Card", "action": "/tech-cards/new", "fields": tech_card_fields(products, statuses, approvers), "back_url": "/tech-cards", "submit_label": "Create Tech Card"})


@router.post("/tech-cards/new")
def tech_card_new(
    request: Request,
    product_id: str = Form(...),
    card_number: str = Form(...),
    version: str = Form(...),
    status_code: str = Form(...),
    effective_from: str = Form(...),
    effective_to: str = Form(""),
    baking_time_min: str = Form(...),
    baking_temperature_c: str = Form(...),
    process_description: str = Form(...),
    approved_by_user_id: str = Form(""),
):
    user = authorize_section(request, "tech_cards")
    if not isinstance(user, dict):
        return user
    products = fetch_all("SELECT product_id, name FROM products WHERE is_active = TRUE ORDER BY name")
    statuses = fetch_all("SELECT status_code, name FROM tech_card_statuses ORDER BY name")
    approvers = fetch_all("SELECT user_id, full_name FROM users WHERE status_code = 'active' ORDER BY full_name")
    form_data = {
        "product_id": product_id,
        "card_number": card_number,
        "version": version,
        "status_code": status_code,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "baking_time_min": baking_time_min,
        "baking_temperature_c": baking_temperature_c,
        "process_description": process_description,
        "approved_by_user_id": approved_by_user_id,
    }
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            tech_card_id = next_id(conn, "tech_cards", "tech_card_id")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tech_cards (
                        tech_card_id, product_id, card_number, version, status_code,
                        effective_from, effective_to, baking_time_min, baking_temperature_c,
                        process_description, approved_by_user_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        tech_card_id,
                        parse_int(product_id, "Product"),
                        clean_text(card_number),
                        parse_int(version, "Version"),
                        clean_text(status_code),
                        parse_date(effective_from, "Effective From"),
                        parse_date(effective_to, "Effective To", allow_none=True),
                        parse_int(baking_time_min, "Baking Time"),
                        parse_decimal(baking_temperature_c, "Baking Temperature"),
                        clean_text(process_description),
                        parse_int(approved_by_user_id, "Approved By", allow_none=True),
                    ),
                )
        set_flash(request, "Tech card created successfully.")
        return redirect_to(f"/tech-cards/{tech_card_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": "Add Tech Card", "action": "/tech-cards/new", "fields": tech_card_fields(products, statuses, approvers, form_data), "back_url": "/tech-cards", "submit_label": "Create Tech Card", "error_message": str(exc)}, status_code=400)


@router.get("/tech-cards/{tech_card_id}")
def tech_card_detail(request: Request, tech_card_id: int):
    user = authorize_section(request, "tech_cards")
    if not isinstance(user, dict):
        return user
    card = fetch_one(
        """
        SELECT tc.*, p.name AS product_name, u.full_name AS approved_by_name
        FROM tech_cards AS tc
        JOIN products AS p ON p.product_id = tc.product_id
        LEFT JOIN users AS u ON u.user_id = tc.approved_by_user_id
        WHERE tc.tech_card_id = %s
        """,
        (tech_card_id,),
    )
    if not card:
        return render_template(request, "error.html", {"title": "Tech card not found", "message": "Tech card record not found."}, status_code=404)
    recipe_rows = fetch_all(
        """
        SELECT
            ri.recipe_item_id,
            rm.name AS material_name,
            ri.quantity,
            ri.unit,
            ri.stage,
            ri.waste_percent,
            ri.note
        FROM recipe_items AS ri
        JOIN raw_materials AS rm ON rm.material_id = ri.material_id
        WHERE ri.tech_card_id = %s
        ORDER BY ri.recipe_item_id
        """,
        (tech_card_id,),
    )
    for row in recipe_rows:
        row["_detail_url"] = f"/recipe-items/{row['recipe_item_id']}/edit"
    return render_template(
        request,
        "detail.html",
        {
            "title": card["card_number"],
            "back_url": "/tech-cards",
            "edit_url": f"/tech-cards/{tech_card_id}/edit",
            "extra_actions": [{"label": "Add Recipe Item", "url": f"/tech-cards/{tech_card_id}/recipe/new"}],
            "details": [
                ("ID", card["tech_card_id"]),
                ("Product", card["product_name"]),
                ("Version", card["version"]),
                ("Status", card["status_code"]),
                ("Effective From", card["effective_from"]),
                ("Effective To", card["effective_to"]),
                ("Baking Time", card["baking_time_min"]),
                ("Baking Temperature", card["baking_temperature_c"]),
                ("Approved By", card["approved_by_name"]),
                ("Process Description", card["process_description"]),
            ],
            "sections": [
                {
                    "title": "Recipe Items",
                    "headers": [("recipe_item_id", "ID"), ("material_name", "Material"), ("quantity", "Quantity"), ("unit", "Unit"), ("stage", "Stage"), ("waste_percent", "Waste %"), ("note", "Note")],
                    "rows": recipe_rows,
                    "empty_message": "No recipe items added yet.",
                }
            ],
        },
    )


@router.get("/tech-cards/{tech_card_id}/edit")
def tech_card_edit_page(request: Request, tech_card_id: int):
    user = authorize_section(request, "tech_cards")
    if not isinstance(user, dict):
        return user
    card = fetch_one("SELECT * FROM tech_cards WHERE tech_card_id = %s", (tech_card_id,))
    if not card:
        return render_template(request, "error.html", {"title": "Tech card not found", "message": "Tech card record not found."}, status_code=404)
    products = fetch_all("SELECT product_id, name FROM products WHERE is_active = TRUE ORDER BY name")
    statuses = fetch_all("SELECT status_code, name FROM tech_card_statuses ORDER BY name")
    approvers = fetch_all("SELECT user_id, full_name FROM users WHERE status_code = 'active' ORDER BY full_name")
    return render_template(request, "form.html", {"title": f"Edit Tech Card #{tech_card_id}", "action": f"/tech-cards/{tech_card_id}/edit", "fields": tech_card_fields(products, statuses, approvers, card), "back_url": f"/tech-cards/{tech_card_id}", "submit_label": "Save Changes"})


@router.post("/tech-cards/{tech_card_id}/edit")
def tech_card_edit(
    request: Request,
    tech_card_id: int,
    product_id: str = Form(...),
    card_number: str = Form(...),
    version: str = Form(...),
    status_code: str = Form(...),
    effective_from: str = Form(...),
    effective_to: str = Form(""),
    baking_time_min: str = Form(...),
    baking_temperature_c: str = Form(...),
    process_description: str = Form(...),
    approved_by_user_id: str = Form(""),
):
    user = authorize_section(request, "tech_cards")
    if not isinstance(user, dict):
        return user
    products = fetch_all("SELECT product_id, name FROM products WHERE is_active = TRUE ORDER BY name")
    statuses = fetch_all("SELECT status_code, name FROM tech_card_statuses ORDER BY name")
    approvers = fetch_all("SELECT user_id, full_name FROM users WHERE status_code = 'active' ORDER BY full_name")
    form_data = {
        "product_id": product_id,
        "card_number": card_number,
        "version": version,
        "status_code": status_code,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "baking_time_min": baking_time_min,
        "baking_temperature_c": baking_temperature_c,
        "process_description": process_description,
        "approved_by_user_id": approved_by_user_id,
    }
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tech_cards
                    SET product_id = %s,
                        card_number = %s,
                        version = %s,
                        status_code = %s,
                        effective_from = %s,
                        effective_to = %s,
                        baking_time_min = %s,
                        baking_temperature_c = %s,
                        process_description = %s,
                        approved_by_user_id = %s
                    WHERE tech_card_id = %s
                    """,
                    (
                        parse_int(product_id, "Product"),
                        clean_text(card_number),
                        parse_int(version, "Version"),
                        clean_text(status_code),
                        parse_date(effective_from, "Effective From"),
                        parse_date(effective_to, "Effective To", allow_none=True),
                        parse_int(baking_time_min, "Baking Time"),
                        parse_decimal(baking_temperature_c, "Baking Temperature"),
                        clean_text(process_description),
                        parse_int(approved_by_user_id, "Approved By", allow_none=True),
                        tech_card_id,
                    ),
                )
        set_flash(request, "Tech card updated successfully.")
        return redirect_to(f"/tech-cards/{tech_card_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"Edit Tech Card #{tech_card_id}", "action": f"/tech-cards/{tech_card_id}/edit", "fields": tech_card_fields(products, statuses, approvers, form_data), "back_url": f"/tech-cards/{tech_card_id}", "submit_label": "Save Changes", "error_message": str(exc)}, status_code=400)


@router.get("/tech-cards/{tech_card_id}/recipe/new")
def recipe_item_new_page(request: Request, tech_card_id: int):
    user = authorize_section(request, "tech_cards")
    if not isinstance(user, dict):
        return user
    materials = fetch_all("SELECT material_id, name FROM raw_materials WHERE is_active = TRUE ORDER BY name")
    return render_template(request, "form.html", {"title": f"Add Recipe Item to Tech Card #{tech_card_id}", "action": f"/tech-cards/{tech_card_id}/recipe/new", "fields": recipe_item_fields(materials), "back_url": f"/tech-cards/{tech_card_id}", "submit_label": "Add Recipe Item"})


@router.post("/tech-cards/{tech_card_id}/recipe/new")
def recipe_item_new(
    request: Request,
    tech_card_id: int,
    material_id: str = Form(...),
    quantity: str = Form(...),
    unit: str = Form(...),
    stage: str = Form(""),
    waste_percent: str = Form("0"),
    note: str = Form(""),
):
    user = authorize_section(request, "tech_cards")
    if not isinstance(user, dict):
        return user
    materials = fetch_all("SELECT material_id, name FROM raw_materials WHERE is_active = TRUE ORDER BY name")
    form_data = {"material_id": material_id, "quantity": quantity, "unit": unit, "stage": stage, "waste_percent": waste_percent, "note": note}
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            recipe_item_id = next_id(conn, "recipe_items", "recipe_item_id")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO recipe_items (
                        recipe_item_id, tech_card_id, material_id, quantity, unit, stage, waste_percent, note
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        recipe_item_id,
                        tech_card_id,
                        parse_int(material_id, "Material"),
                        parse_decimal(quantity, "Quantity"),
                        clean_text(unit),
                        clean_text(stage),
                        parse_decimal(waste_percent, "Waste Percent"),
                        clean_text(note),
                    ),
                )
        set_flash(request, "Recipe item added successfully.")
        return redirect_to(f"/tech-cards/{tech_card_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"Add Recipe Item to Tech Card #{tech_card_id}", "action": f"/tech-cards/{tech_card_id}/recipe/new", "fields": recipe_item_fields(materials, form_data), "back_url": f"/tech-cards/{tech_card_id}", "submit_label": "Add Recipe Item", "error_message": str(exc)}, status_code=400)


@router.get("/recipe-items/{recipe_item_id}/edit")
def recipe_item_edit_page(request: Request, recipe_item_id: int):
    user = authorize_section(request, "tech_cards")
    if not isinstance(user, dict):
        return user
    item = fetch_one("SELECT * FROM recipe_items WHERE recipe_item_id = %s", (recipe_item_id,))
    if not item:
        return render_template(request, "error.html", {"title": "Recipe item not found", "message": "Recipe item record not found."}, status_code=404)
    materials = fetch_all("SELECT material_id, name FROM raw_materials WHERE is_active = TRUE ORDER BY name")
    return render_template(request, "form.html", {"title": f"Edit Recipe Item #{recipe_item_id}", "action": f"/recipe-items/{recipe_item_id}/edit", "fields": recipe_item_fields(materials, item), "back_url": f"/tech-cards/{item['tech_card_id']}", "submit_label": "Save Changes"})


@router.post("/recipe-items/{recipe_item_id}/edit")
def recipe_item_edit(
    request: Request,
    recipe_item_id: int,
    material_id: str = Form(...),
    quantity: str = Form(...),
    unit: str = Form(...),
    stage: str = Form(""),
    waste_percent: str = Form("0"),
    note: str = Form(""),
):
    user = authorize_section(request, "tech_cards")
    if not isinstance(user, dict):
        return user
    item = fetch_one("SELECT tech_card_id FROM recipe_items WHERE recipe_item_id = %s", (recipe_item_id,))
    if not item:
        return render_template(request, "error.html", {"title": "Recipe item not found", "message": "Recipe item record not found."}, status_code=404)
    materials = fetch_all("SELECT material_id, name FROM raw_materials WHERE is_active = TRUE ORDER BY name")
    form_data = {"material_id": material_id, "quantity": quantity, "unit": unit, "stage": stage, "waste_percent": waste_percent, "note": note}
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE recipe_items
                    SET material_id = %s,
                        quantity = %s,
                        unit = %s,
                        stage = %s,
                        waste_percent = %s,
                        note = %s
                    WHERE recipe_item_id = %s
                    """,
                    (
                        parse_int(material_id, "Material"),
                        parse_decimal(quantity, "Quantity"),
                        clean_text(unit),
                        clean_text(stage),
                        parse_decimal(waste_percent, "Waste Percent"),
                        clean_text(note),
                        recipe_item_id,
                    ),
                )
        set_flash(request, "Recipe item updated successfully.")
        return redirect_to(f"/tech-cards/{item['tech_card_id']}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"Edit Recipe Item #{recipe_item_id}", "action": f"/recipe-items/{recipe_item_id}/edit", "fields": recipe_item_fields(materials, form_data), "back_url": f"/tech-cards/{item['tech_card_id']}", "submit_label": "Save Changes", "error_message": str(exc)}, status_code=400)
