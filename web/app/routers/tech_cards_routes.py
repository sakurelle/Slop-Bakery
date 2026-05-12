from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_action, authorize_section, forbidden_response, redirect_to, render_template, set_flash
from ..database import fetch_all, fetch_one, get_db
from ..permissions import has_action
from ..utils import build_options, clean_text, parse_date, parse_decimal, parse_int


router = APIRouter()

TECH_CARD_STATUS_TRANSITIONS = {
    "draft": {"active", "archived"},
    "active": {"archived"},
    "archived": set(),
}


def tech_card_fields(products, approvers, data=None):
    data = data or {}
    return [
        {
            "name": "product_id",
            "label": "РџСЂРѕРґСѓРєС†РёСЏ",
            "type": "select",
            "required": True,
            "value": data.get("product_id", ""),
            "options": build_options(products, "product_id", "name"),
        },
        {"name": "card_number", "label": "РќРѕРјРµСЂ РєР°СЂС‚С‹", "type": "text", "required": True, "value": data.get("card_number", "")},
        {"name": "version", "label": "Р’РµСЂСЃРёСЏ", "type": "number", "required": True, "min": "1", "value": data.get("version", "1")},
        {"name": "effective_from", "label": "Р”РµР№СЃС‚РІСѓРµС‚ СЃ", "type": "date", "required": True, "value": data.get("effective_from", "")},
        {"name": "effective_to", "label": "Р”РµР№СЃС‚РІСѓРµС‚ РґРѕ", "type": "date", "value": data.get("effective_to", "")},
        {"name": "baking_time_min", "label": "Р’СЂРµРјСЏ РІС‹РїРµС‡РєРё (РјРёРЅ)", "type": "number", "required": True, "min": "1", "value": data.get("baking_time_min", "")},
        {"name": "baking_temperature_c", "label": "РўРµРјРїРµСЂР°С‚СѓСЂР° РІС‹РїРµС‡РєРё (C)", "type": "number", "required": True, "step": "0.01", "min": "0.01", "value": data.get("baking_temperature_c", "")},
        {"name": "process_description", "label": "РћРїРёСЃР°РЅРёРµ РїСЂРѕС†РµСЃСЃР°", "type": "textarea", "required": True, "value": data.get("process_description", "")},
        {
            "name": "approved_by_user_id",
            "label": "РЈС‚РІРµСЂРґРёР»",
            "type": "select",
            "value": data.get("approved_by_user_id", ""),
            "options": build_options(approvers, "user_id", "full_name", blank_label="РџРѕРєР° РЅРµ СѓС‚РІРµСЂР¶РґРµРЅРѕ"),
        },
    ]


def recipe_item_fields(materials, data=None):
    data = data or {}
    return [
        {
            "name": "material_id",
            "label": "РЎС‹СЂСЊС‘",
            "type": "select",
            "required": True,
            "value": data.get("material_id", ""),
            "options": build_options(materials, "material_id", "name"),
        },
        {"name": "quantity", "label": "РљРѕР»РёС‡РµСЃС‚РІРѕ", "type": "number", "required": True, "step": "0.001", "min": "0.001", "value": data.get("quantity", "")},
        {"name": "unit", "label": "Р•РґРёРЅРёС†Р° РёР·РјРµСЂРµРЅРёСЏ", "type": "text", "required": True, "value": data.get("unit", "kg")},
        {"name": "stage", "label": "Р­С‚Р°Рї", "type": "text", "value": data.get("stage", "")},
        {"name": "waste_percent", "label": "РџСЂРѕС†РµРЅС‚ РїРѕС‚РµСЂСЊ", "type": "number", "step": "0.01", "min": "0", "max": "99.99", "value": data.get("waste_percent", "0")},
        {"name": "note", "label": "РџСЂРёРјРµС‡Р°РЅРёРµ", "type": "textarea", "value": data.get("note", "")},
    ]


def tech_card_status_fields(statuses, current_status):
    return [{"name": "status_code", "label": "РЎС‚Р°С‚СѓСЃ", "type": "select", "required": True, "value": current_status, "options": build_options(statuses, "status_code", "name")}]


def get_approver_options():
    return fetch_all(
        """
        SELECT DISTINCT u.user_id, u.full_name
        FROM users AS u
        JOIN user_roles AS ur ON ur.user_id = u.user_id
        JOIN roles AS r ON r.role_id = ur.role_id
        WHERE u.status_code = 'active'
          AND r.role_code IN ('admin', 'technologist')
        ORDER BY u.full_name
        """
    )


def fetch_tech_card(tech_card_id: int):
    return fetch_one(
        """
        SELECT tc.*, p.name AS product_name, u.full_name AS approved_by_name
        FROM tech_cards AS tc
        JOIN products AS p ON p.product_id = tc.product_id
        LEFT JOIN users AS u ON u.user_id = tc.approved_by_user_id
        WHERE tc.tech_card_id = %s
        """,
        (tech_card_id,),
    )


def tech_card_used_in_production(tech_card_id: int) -> bool:
    row = fetch_one("SELECT 1 AS used FROM production_batches WHERE tech_card_id = %s LIMIT 1", (tech_card_id,))
    return bool(row)


def recipe_edit_allowed(card: dict) -> bool:
    return card["status_code"] == "draft" and not tech_card_used_in_production(card["tech_card_id"])


def validate_approver(conn, approved_by_user_id):
    if approved_by_user_id is None:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM users AS u
            JOIN user_roles AS ur ON ur.user_id = u.user_id
            JOIN roles AS r ON r.role_id = ur.role_id
            WHERE u.user_id = %s
              AND u.status_code = 'active'
              AND r.role_code IN ('admin', 'technologist')
            LIMIT 1
            """,
            (approved_by_user_id,),
        )
        if not cur.fetchone():
            raise ValueError("РЈС‚РІРµСЂР¶РґР°СЋС‰РёРј РјРѕР¶РµС‚ Р±С‹С‚СЊ С‚РѕР»СЊРєРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ РёР»Рё С‚РµС…РЅРѕР»РѕРі.")


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
    context = {
        "title": "РўРµС…РЅРѕР»РѕРіРёС‡РµСЃРєРёРµ РєР°СЂС‚С‹",
        "subtitle": "РўРµС…РЅРѕР»РѕРіРёС‡РµСЃРєРёРµ РєР°СЂС‚С‹ РїСЂРѕРґСѓРєС†РёРё Рё СЃРѕСЃС‚Р°РІ СЂРµС†РµРїС‚СѓСЂ.",
        "headers": [
            ("tech_card_id", "ID"),
            ("card_number", "РќРѕРјРµСЂ РєР°СЂС‚С‹"),
            ("product_name", "РџСЂРѕРґСѓРєС†РёСЏ"),
            ("version", "Р’РµСЂСЃРёСЏ"),
            ("status_code", "РЎС‚Р°С‚СѓСЃ"),
            ("effective_from", "Р”РµР№СЃС‚РІСѓРµС‚ СЃ"),
            ("effective_to", "Р”РµР№СЃС‚РІСѓРµС‚ РґРѕ"),
        ],
        "rows": rows,
    }
    if has_action(user, "tech_cards.manage"):
        context["create_url"] = "/tech-cards/new"
        context["create_label"] = "Р”РѕР±Р°РІРёС‚СЊ С‚РµС…РєР°СЂС‚Сѓ"
    return render_template(request, "table_list.html", context)


@router.get("/tech-cards/new")
def tech_card_new_page(request: Request):
    user = authorize_action(request, "tech_cards.manage", "РЈ РІР°СЃ РЅРµС‚ РїСЂР°РІ РЅР° СѓРїСЂР°РІР»РµРЅРёРµ С‚РµС…РЅРѕР»РѕРіРёС‡РµСЃРєРёРјРё РєР°СЂС‚Р°РјРё.")
    if not isinstance(user, dict):
        return user
    products = fetch_all("SELECT product_id, name FROM products WHERE is_active = TRUE ORDER BY name")
    approvers = get_approver_options()
    return render_template(request, "form.html", {"title": "Р”РѕР±Р°РІРёС‚СЊ С‚РµС…РєР°СЂС‚Сѓ", "action": "/tech-cards/new", "fields": tech_card_fields(products, approvers), "back_url": "/tech-cards", "submit_label": "РЎРѕР·РґР°С‚СЊ С‚РµС…РєР°СЂС‚Сѓ"})


@router.post("/tech-cards/new")
def tech_card_new(
    request: Request,
    product_id: str = Form(...),
    card_number: str = Form(...),
    version: str = Form(...),
    effective_from: str = Form(...),
    effective_to: str = Form(""),
    baking_time_min: str = Form(...),
    baking_temperature_c: str = Form(...),
    process_description: str = Form(...),
    approved_by_user_id: str = Form(""),
):
    user = authorize_action(request, "tech_cards.manage", "РЈ РІР°СЃ РЅРµС‚ РїСЂР°РІ РЅР° СѓРїСЂР°РІР»РµРЅРёРµ С‚РµС…РЅРѕР»РѕРіРёС‡РµСЃРєРёРјРё РєР°СЂС‚Р°РјРё.")
    if not isinstance(user, dict):
        return user
    products = fetch_all("SELECT product_id, name FROM products WHERE is_active = TRUE ORDER BY name")
    approvers = get_approver_options()
    form_data = {
        "product_id": product_id,
        "card_number": card_number,
        "version": version,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "baking_time_min": baking_time_min,
        "baking_temperature_c": baking_temperature_c,
        "process_description": process_description,
        "approved_by_user_id": approved_by_user_id,
    }
    try:
        approved_by = parse_int(approved_by_user_id, "РЈС‚РІРµСЂРґРёР»", allow_none=True)
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            validate_approver(conn, approved_by)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tech_cards (
                        product_id, card_number, version, status_code,
                        effective_from, effective_to, baking_time_min, baking_temperature_c,
                        process_description, approved_by_user_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING tech_card_id
                    """,
                    (
                        parse_int(product_id, "РџСЂРѕРґСѓРєС†РёСЏ"),
                        clean_text(card_number),
                        parse_int(version, "Р’РµСЂСЃРёСЏ"),
                        "draft",
                        parse_date(effective_from, "Р”РµР№СЃС‚РІСѓРµС‚ СЃ"),
                        parse_date(effective_to, "Р”РµР№СЃС‚РІСѓРµС‚ РґРѕ", allow_none=True),
                        parse_int(baking_time_min, "Р’СЂРµРјСЏ РІС‹РїРµС‡РєРё"),
                        parse_decimal(baking_temperature_c, "РўРµРјРїРµСЂР°С‚СѓСЂР° РІС‹РїРµС‡РєРё"),
                        clean_text(process_description),
                        approved_by,
                    ),
                )
                tech_card_id = cur.fetchone()["tech_card_id"]
        set_flash(request, "РўРµС…РЅРѕР»РѕРіРёС‡РµСЃРєР°СЏ РєР°СЂС‚Р° СЃРѕР·РґР°РЅР° СЃРѕ СЃС‚Р°С‚СѓСЃРѕРј В«Р§РµСЂРЅРѕРІРёРєВ».")
        return redirect_to(f"/tech-cards/{tech_card_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": "Р”РѕР±Р°РІРёС‚СЊ С‚РµС…РєР°СЂС‚Сѓ", "action": "/tech-cards/new", "fields": tech_card_fields(products, approvers, form_data), "back_url": "/tech-cards", "submit_label": "РЎРѕР·РґР°С‚СЊ С‚РµС…РєР°СЂС‚Сѓ", "error_message": str(exc)}, status_code=400)


@router.get("/tech-cards/{tech_card_id}")
def tech_card_detail(request: Request, tech_card_id: int):
    user = authorize_section(request, "tech_cards")
    if not isinstance(user, dict):
        return user
    card = fetch_tech_card(tech_card_id)
    if not card:
        return render_template(request, "error.html", {"title": "РўРµС…РєР°СЂС‚Р° РЅРµ РЅР°Р№РґРµРЅР°", "message": "РљР°СЂС‚РѕС‡РєР° С‚РµС…РєР°СЂС‚С‹ РЅРµ РЅР°Р№РґРµРЅР°."}, status_code=404)
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
    if recipe_edit_allowed(card):
        for row in recipe_rows:
            row["_detail_url"] = f"/recipe-items/{row['recipe_item_id']}/edit"
    extra_actions = []
    if recipe_edit_allowed(card) and has_action(user, "tech_cards.manage"):
        extra_actions.append({"label": "Р”РѕР±Р°РІРёС‚СЊ РёРЅРіСЂРµРґРёРµРЅС‚", "url": f"/tech-cards/{tech_card_id}/recipe/new"})
    if has_action(user, "tech_cards.manage") and card["status_code"] == "draft":
        extra_actions.append({"label": "Р РµРґР°РєС‚РёСЂРѕРІР°С‚СЊ", "url": f"/tech-cards/{tech_card_id}/edit"})
    if has_action(user, "tech_cards.change_status"):
        extra_actions.append({"label": "РР·РјРµРЅРёС‚СЊ СЃС‚Р°С‚СѓСЃ", "url": f"/tech-cards/{tech_card_id}/status"})
    return render_template(
        request,
        "detail.html",
        {
            "title": card["card_number"],
            "back_url": "/tech-cards",
            "extra_actions": extra_actions,
            "details": [
                ("ID", card["tech_card_id"]),
                ("РџСЂРѕРґСѓРєС†РёСЏ", card["product_name"]),
                ("Р’РµСЂСЃРёСЏ", card["version"]),
                ("РЎС‚Р°С‚СѓСЃ", card["status_code"]),
                ("Р”РµР№СЃС‚РІСѓРµС‚ СЃ", card["effective_from"]),
                ("Р”РµР№СЃС‚РІСѓРµС‚ РґРѕ", card["effective_to"]),
                ("Р’СЂРµРјСЏ РІС‹РїРµС‡РєРё", card["baking_time_min"]),
                ("РўРµРјРїРµСЂР°С‚СѓСЂР° РІС‹РїРµС‡РєРё", card["baking_temperature_c"]),
                ("РЈС‚РІРµСЂРґРёР»", card["approved_by_name"]),
                ("РћРїРёСЃР°РЅРёРµ РїСЂРѕС†РµСЃСЃР°", card["process_description"]),
            ],
            "sections": [
                {
                    "title": "РЎРѕСЃС‚Р°РІ СЂРµС†РµРїС‚СѓСЂС‹",
                    "headers": [("recipe_item_id", "ID"), ("material_name", "РЎС‹СЂСЊС‘"), ("quantity", "РљРѕР»РёС‡РµСЃС‚РІРѕ"), ("unit", "Р•Рґ."), ("stage", "Р­С‚Р°Рї"), ("waste_percent", "РџРѕС‚РµСЂРё %"), ("note", "РџСЂРёРјРµС‡Р°РЅРёРµ")],
                    "rows": recipe_rows,
                    "empty_message": "РЎРѕСЃС‚Р°РІ СЂРµС†РµРїС‚СѓСЂС‹ РµС‰С‘ РЅРµ Р·Р°РїРѕР»РЅРµРЅ.",
                }
            ],
        },
    )


@router.get("/tech-cards/{tech_card_id}/edit")
def tech_card_edit_page(request: Request, tech_card_id: int):
    user = authorize_action(request, "tech_cards.manage", "РЈ РІР°СЃ РЅРµС‚ РїСЂР°РІ РЅР° СѓРїСЂР°РІР»РµРЅРёРµ С‚РµС…РЅРѕР»РѕРіРёС‡РµСЃРєРёРјРё РєР°СЂС‚Р°РјРё.")
    if not isinstance(user, dict):
        return user
    card = fetch_one("SELECT * FROM tech_cards WHERE tech_card_id = %s", (tech_card_id,))
    if not card:
        return render_template(request, "error.html", {"title": "РўРµС…РєР°СЂС‚Р° РЅРµ РЅР°Р№РґРµРЅР°", "message": "РљР°СЂС‚РѕС‡РєР° С‚РµС…РєР°СЂС‚С‹ РЅРµ РЅР°Р№РґРµРЅР°."}, status_code=404)
    if card["status_code"] != "draft":
        return forbidden_response(request, "Р РµРґР°РєС‚РёСЂРѕРІР°С‚СЊ РјРѕР¶РЅРѕ С‚РѕР»СЊРєРѕ С‡РµСЂРЅРѕРІРёРє С‚РµС…РєР°СЂС‚С‹.")
    products = fetch_all("SELECT product_id, name FROM products WHERE is_active = TRUE ORDER BY name")
    approvers = get_approver_options()
    return render_template(request, "form.html", {"title": f"Р РµРґР°РєС‚РёСЂРѕРІР°С‚СЊ С‚РµС…РєР°СЂС‚Сѓ #{tech_card_id}", "action": f"/tech-cards/{tech_card_id}/edit", "fields": tech_card_fields(products, approvers, card), "back_url": f"/tech-cards/{tech_card_id}", "submit_label": "РЎРѕС…СЂР°РЅРёС‚СЊ РёР·РјРµРЅРµРЅРёСЏ"})


@router.post("/tech-cards/{tech_card_id}/edit")
def tech_card_edit(
    request: Request,
    tech_card_id: int,
    product_id: str = Form(...),
    card_number: str = Form(...),
    version: str = Form(...),
    effective_from: str = Form(...),
    effective_to: str = Form(""),
    baking_time_min: str = Form(...),
    baking_temperature_c: str = Form(...),
    process_description: str = Form(...),
    approved_by_user_id: str = Form(""),
):
    user = authorize_action(request, "tech_cards.manage", "РЈ РІР°СЃ РЅРµС‚ РїСЂР°РІ РЅР° СѓРїСЂР°РІР»РµРЅРёРµ С‚РµС…РЅРѕР»РѕРіРёС‡РµСЃРєРёРјРё РєР°СЂС‚Р°РјРё.")
    if not isinstance(user, dict):
        return user
    card = fetch_one("SELECT * FROM tech_cards WHERE tech_card_id = %s", (tech_card_id,))
    if not card:
        return render_template(request, "error.html", {"title": "РўРµС…РєР°СЂС‚Р° РЅРµ РЅР°Р№РґРµРЅР°", "message": "РљР°СЂС‚РѕС‡РєР° С‚РµС…РєР°СЂС‚С‹ РЅРµ РЅР°Р№РґРµРЅР°."}, status_code=404)
    if card["status_code"] != "draft":
        return forbidden_response(request, "Р РµРґР°РєС‚РёСЂРѕРІР°С‚СЊ РјРѕР¶РЅРѕ С‚РѕР»СЊРєРѕ С‡РµСЂРЅРѕРІРёРє С‚РµС…РєР°СЂС‚С‹.")
    products = fetch_all("SELECT product_id, name FROM products WHERE is_active = TRUE ORDER BY name")
    approvers = get_approver_options()
    form_data = {
        "product_id": product_id,
        "card_number": card_number,
        "version": version,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "baking_time_min": baking_time_min,
        "baking_temperature_c": baking_temperature_c,
        "process_description": process_description,
        "approved_by_user_id": approved_by_user_id,
    }
    try:
        approved_by = parse_int(approved_by_user_id, "РЈС‚РІРµСЂРґРёР»", allow_none=True)
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            validate_approver(conn, approved_by)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tech_cards
                    SET product_id = %s,
                        card_number = %s,
                        version = %s,
                        effective_from = %s,
                        effective_to = %s,
                        baking_time_min = %s,
                        baking_temperature_c = %s,
                        process_description = %s,
                        approved_by_user_id = %s
                    WHERE tech_card_id = %s
                    """,
                    (
                        parse_int(product_id, "РџСЂРѕРґСѓРєС†РёСЏ"),
                        clean_text(card_number),
                        parse_int(version, "Р’РµСЂСЃРёСЏ"),
                        parse_date(effective_from, "Р”РµР№СЃС‚РІСѓРµС‚ СЃ"),
                        parse_date(effective_to, "Р”РµР№СЃС‚РІСѓРµС‚ РґРѕ", allow_none=True),
                        parse_int(baking_time_min, "Р’СЂРµРјСЏ РІС‹РїРµС‡РєРё"),
                        parse_decimal(baking_temperature_c, "РўРµРјРїРµСЂР°С‚СѓСЂР° РІС‹РїРµС‡РєРё"),
                        clean_text(process_description),
                        approved_by,
                        tech_card_id,
                    ),
                )
        set_flash(request, "РўРµС…РЅРѕР»РѕРіРёС‡РµСЃРєР°СЏ РєР°СЂС‚Р° СѓСЃРїРµС€РЅРѕ РѕР±РЅРѕРІР»РµРЅР°.")
        return redirect_to(f"/tech-cards/{tech_card_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"Р РµРґР°РєС‚РёСЂРѕРІР°С‚СЊ С‚РµС…РєР°СЂС‚Сѓ #{tech_card_id}", "action": f"/tech-cards/{tech_card_id}/edit", "fields": tech_card_fields(products, approvers, form_data), "back_url": f"/tech-cards/{tech_card_id}", "submit_label": "РЎРѕС…СЂР°РЅРёС‚СЊ РёР·РјРµРЅРµРЅРёСЏ", "error_message": str(exc)}, status_code=400)


@router.get("/tech-cards/{tech_card_id}/status")
def tech_card_status_page(request: Request, tech_card_id: int):
    user = authorize_action(request, "tech_cards.change_status", "РЈ РІР°СЃ РЅРµС‚ РїСЂР°РІ РЅР° РёР·РјРµРЅРµРЅРёРµ СЃС‚Р°С‚СѓСЃР° С‚РµС…РєР°СЂС‚С‹.")
    if not isinstance(user, dict):
        return user
    card = fetch_one("SELECT tech_card_id, status_code FROM tech_cards WHERE tech_card_id = %s", (tech_card_id,))
    if not card:
        return render_template(request, "error.html", {"title": "РўРµС…РєР°СЂС‚Р° РЅРµ РЅР°Р№РґРµРЅР°", "message": "РљР°СЂС‚РѕС‡РєР° С‚РµС…РєР°СЂС‚С‹ РЅРµ РЅР°Р№РґРµРЅР°."}, status_code=404)
    allowed = TECH_CARD_STATUS_TRANSITIONS.get(card["status_code"], set())
    statuses = fetch_all("SELECT status_code, name FROM tech_card_statuses WHERE status_code = ANY(%s) ORDER BY name", (sorted(allowed),)) if allowed else []
    if not statuses:
        return forbidden_response(request, "Р”Р»СЏ С‚РµРєСѓС‰РµРіРѕ СЃС‚Р°С‚СѓСЃР° С‚РµС…РєР°СЂС‚С‹ РЅРµС‚ РґРѕРїСѓСЃС‚РёРјС‹С… РїРµСЂРµС…РѕРґРѕРІ.")
    return render_template(request, "form.html", {"title": f"РР·РјРµРЅРёС‚СЊ СЃС‚Р°С‚СѓСЃ С‚РµС…РєР°СЂС‚С‹ #{tech_card_id}", "action": f"/tech-cards/{tech_card_id}/status", "fields": tech_card_status_fields(statuses, statuses[0]['status_code']), "back_url": f"/tech-cards/{tech_card_id}", "submit_label": "РћР±РЅРѕРІРёС‚СЊ СЃС‚Р°С‚СѓСЃ"})


@router.post("/tech-cards/{tech_card_id}/status")
def tech_card_status_update(request: Request, tech_card_id: int, status_code: str = Form(...)):
    user = authorize_action(request, "tech_cards.change_status", "РЈ РІР°СЃ РЅРµС‚ РїСЂР°РІ РЅР° РёР·РјРµРЅРµРЅРёРµ СЃС‚Р°С‚СѓСЃР° С‚РµС…РєР°СЂС‚С‹.")
    if not isinstance(user, dict):
        return user
    card = fetch_one("SELECT * FROM tech_cards WHERE tech_card_id = %s", (tech_card_id,))
    if not card:
        return render_template(request, "error.html", {"title": "РўРµС…РєР°СЂС‚Р° РЅРµ РЅР°Р№РґРµРЅР°", "message": "РљР°СЂС‚РѕС‡РєР° С‚РµС…РєР°СЂС‚С‹ РЅРµ РЅР°Р№РґРµРЅР°."}, status_code=404)
    new_status = clean_text(status_code)
    allowed = TECH_CARD_STATUS_TRANSITIONS.get(card["status_code"], set())
    statuses = fetch_all("SELECT status_code, name FROM tech_card_statuses WHERE status_code = ANY(%s) ORDER BY name", (sorted(allowed),)) if allowed else []
    try:
        if new_status not in allowed:
            raise ValueError("РќРµРґРѕРїСѓСЃС‚РёРјС‹Р№ РїРµСЂРµС…РѕРґ СЃС‚Р°С‚СѓСЃР° С‚РµС…РєР°СЂС‚С‹.")
        if new_status == "active" and not card["approved_by_user_id"]:
            raise ValueError("РџРµСЂРµРґ Р°РєС‚РёРІР°С†РёРµР№ РЅСѓР¶РЅРѕ СѓРєР°Р·Р°С‚СЊ СѓС‚РІРµСЂР¶РґР°СЋС‰РµРіРѕ.")
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE tech_cards SET status_code = %s WHERE tech_card_id = %s", (new_status, tech_card_id))
        set_flash(request, "РЎС‚Р°С‚СѓСЃ С‚РµС…РєР°СЂС‚С‹ СѓСЃРїРµС€РЅРѕ РѕР±РЅРѕРІР»С‘РЅ.")
        return redirect_to(f"/tech-cards/{tech_card_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"РР·РјРµРЅРёС‚СЊ СЃС‚Р°С‚СѓСЃ С‚РµС…РєР°СЂС‚С‹ #{tech_card_id}", "action": f"/tech-cards/{tech_card_id}/status", "fields": tech_card_status_fields(statuses, new_status or card['status_code']), "back_url": f"/tech-cards/{tech_card_id}", "submit_label": "РћР±РЅРѕРІРёС‚СЊ СЃС‚Р°С‚СѓСЃ", "error_message": str(exc)}, status_code=400)


@router.get("/tech-cards/{tech_card_id}/recipe/new")
def recipe_item_new_page(request: Request, tech_card_id: int):
    user = authorize_action(request, "tech_cards.manage", "РЈ РІР°СЃ РЅРµС‚ РїСЂР°РІ РЅР° СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ СЂРµС†РµРїС‚СѓСЂС‹.")
    if not isinstance(user, dict):
        return user
    card = fetch_tech_card(tech_card_id)
    if not card:
        return render_template(request, "error.html", {"title": "РўРµС…РєР°СЂС‚Р° РЅРµ РЅР°Р№РґРµРЅР°", "message": "РљР°СЂС‚РѕС‡РєР° С‚РµС…РєР°СЂС‚С‹ РЅРµ РЅР°Р№РґРµРЅР°."}, status_code=404)
    if not recipe_edit_allowed(card):
        return forbidden_response(request, "Р РµС†РµРїС‚СѓСЂСѓ РјРѕР¶РЅРѕ СЂРµРґР°РєС‚РёСЂРѕРІР°С‚СЊ С‚РѕР»СЊРєРѕ Сѓ РЅРµРёСЃРїРѕР»СЊР·РѕРІР°РЅРЅРѕРіРѕ С‡РµСЂРЅРѕРІРёРєР° С‚РµС…РєР°СЂС‚С‹.")
    materials = fetch_all("SELECT material_id, name FROM raw_materials WHERE is_active = TRUE ORDER BY name")
    return render_template(request, "form.html", {"title": f"Р”РѕР±Р°РІРёС‚СЊ РёРЅРіСЂРµРґРёРµРЅС‚ РІ С‚РµС…РєР°СЂС‚Сѓ #{tech_card_id}", "action": f"/tech-cards/{tech_card_id}/recipe/new", "fields": recipe_item_fields(materials), "back_url": f"/tech-cards/{tech_card_id}", "submit_label": "Р”РѕР±Р°РІРёС‚СЊ РёРЅРіСЂРµРґРёРµРЅС‚"})


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
    user = authorize_action(request, "tech_cards.manage", "РЈ РІР°СЃ РЅРµС‚ РїСЂР°РІ РЅР° СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ СЂРµС†РµРїС‚СѓСЂС‹.")
    if not isinstance(user, dict):
        return user
    card = fetch_tech_card(tech_card_id)
    if not card:
        return render_template(request, "error.html", {"title": "РўРµС…РєР°СЂС‚Р° РЅРµ РЅР°Р№РґРµРЅР°", "message": "РљР°СЂС‚РѕС‡РєР° С‚РµС…РєР°СЂС‚С‹ РЅРµ РЅР°Р№РґРµРЅР°."}, status_code=404)
    if not recipe_edit_allowed(card):
        return forbidden_response(request, "Р РµС†РµРїС‚СѓСЂСѓ РјРѕР¶РЅРѕ СЂРµРґР°РєС‚РёСЂРѕРІР°С‚СЊ С‚РѕР»СЊРєРѕ Сѓ РЅРµРёСЃРїРѕР»СЊР·РѕРІР°РЅРЅРѕРіРѕ С‡РµСЂРЅРѕРІРёРєР° С‚РµС…РєР°СЂС‚С‹.")
    materials = fetch_all("SELECT material_id, name FROM raw_materials WHERE is_active = TRUE ORDER BY name")
    form_data = {"material_id": material_id, "quantity": quantity, "unit": unit, "stage": stage, "waste_percent": waste_percent, "note": note}
    try:
        material_id_value = parse_int(material_id, "РЎС‹СЂСЊС‘")
        quantity_value = parse_decimal(quantity, "РљРѕР»РёС‡РµСЃС‚РІРѕ")
        waste_value = parse_decimal(waste_percent, "РџСЂРѕС†РµРЅС‚ РїРѕС‚РµСЂСЊ")
        stage_value = clean_text(stage)
        unit_value = clean_text(unit)
        note_value = clean_text(note)
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT recipe_item_id, quantity
                    FROM recipe_items
                    WHERE tech_card_id = %s
                      AND material_id = %s
                      AND COALESCE(stage, '') = COALESCE(%s, '')
                    """,
                    (tech_card_id, material_id_value, stage_value),
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        """
                        UPDATE recipe_items
                        SET quantity = %s,
                            unit = %s,
                            waste_percent = %s,
                            note = %s
                        WHERE recipe_item_id = %s
                        """,
                        (quantity_value, unit_value, waste_value, note_value, existing["recipe_item_id"]),
                    )
                    set_flash(request, "РЎС‹СЂСЊС‘ СѓР¶Рµ Р±С‹Р»Рѕ РЅР° СЌС‚РѕРј СЌС‚Р°РїРµ, Р·РЅР°С‡РµРЅРёРµ РѕР±РЅРѕРІР»РµРЅРѕ.")
                else:
                    cur.execute(
                        """
                        INSERT INTO recipe_items (
                            tech_card_id, material_id, quantity, unit, stage, waste_percent, note
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            tech_card_id,
                            material_id_value,
                            quantity_value,
                            unit_value,
                            stage_value,
                            waste_value,
                            note_value,
                        ),
                    )
                    set_flash(request, "РРЅРіСЂРµРґРёРµРЅС‚ СЂРµС†РµРїС‚СѓСЂС‹ СѓСЃРїРµС€РЅРѕ РґРѕР±Р°РІР»РµРЅ.")
        return redirect_to(f"/tech-cards/{tech_card_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"Р”РѕР±Р°РІРёС‚СЊ РёРЅРіСЂРµРґРёРµРЅС‚ РІ С‚РµС…РєР°СЂС‚Сѓ #{tech_card_id}", "action": f"/tech-cards/{tech_card_id}/recipe/new", "fields": recipe_item_fields(materials, form_data), "back_url": f"/tech-cards/{tech_card_id}", "submit_label": "Р”РѕР±Р°РІРёС‚СЊ РёРЅРіСЂРµРґРёРµРЅС‚", "error_message": str(exc)}, status_code=400)


@router.get("/recipe-items/{recipe_item_id}/edit")
def recipe_item_edit_page(request: Request, recipe_item_id: int):
    user = authorize_action(request, "tech_cards.manage", "РЈ РІР°СЃ РЅРµС‚ РїСЂР°РІ РЅР° СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ СЂРµС†РµРїС‚СѓСЂС‹.")
    if not isinstance(user, dict):
        return user
    item = fetch_one("SELECT * FROM recipe_items WHERE recipe_item_id = %s", (recipe_item_id,))
    if not item:
        return render_template(request, "error.html", {"title": "РРЅРіСЂРµРґРёРµРЅС‚ РЅРµ РЅР°Р№РґРµРЅ", "message": "Р—Р°РїРёСЃСЊ РёРЅРіСЂРµРґРёРµРЅС‚Р° РЅРµ РЅР°Р№РґРµРЅР°."}, status_code=404)
    card = fetch_tech_card(item["tech_card_id"])
    if not card or not recipe_edit_allowed(card):
        return forbidden_response(request, "Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ РёРЅРіСЂРµРґРёРµРЅС‚Р° РЅРµРґРѕСЃС‚СѓРїРЅРѕ РґР»СЏ СЌС‚РѕР№ С‚РµС…РєР°СЂС‚С‹.")
    materials = fetch_all("SELECT material_id, name FROM raw_materials WHERE is_active = TRUE ORDER BY name")
    return render_template(request, "form.html", {"title": f"Р РµРґР°РєС‚РёСЂРѕРІР°С‚СЊ РёРЅРіСЂРµРґРёРµРЅС‚ #{recipe_item_id}", "action": f"/recipe-items/{recipe_item_id}/edit", "fields": recipe_item_fields(materials, item), "back_url": f"/tech-cards/{item['tech_card_id']}", "submit_label": "РЎРѕС…СЂР°РЅРёС‚СЊ РёР·РјРµРЅРµРЅРёСЏ"})


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
    user = authorize_action(request, "tech_cards.manage", "РЈ РІР°СЃ РЅРµС‚ РїСЂР°РІ РЅР° СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ СЂРµС†РµРїС‚СѓСЂС‹.")
    if not isinstance(user, dict):
        return user
    item = fetch_one("SELECT * FROM recipe_items WHERE recipe_item_id = %s", (recipe_item_id,))
    if not item:
        return render_template(request, "error.html", {"title": "РРЅРіСЂРµРґРёРµРЅС‚ РЅРµ РЅР°Р№РґРµРЅ", "message": "Р—Р°РїРёСЃСЊ РёРЅРіСЂРµРґРёРµРЅС‚Р° РЅРµ РЅР°Р№РґРµРЅР°."}, status_code=404)
    card = fetch_tech_card(item["tech_card_id"])
    if not card or not recipe_edit_allowed(card):
        return forbidden_response(request, "Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ РёРЅРіСЂРµРґРёРµРЅС‚Р° РЅРµРґРѕСЃС‚СѓРїРЅРѕ РґР»СЏ СЌС‚РѕР№ С‚РµС…РєР°СЂС‚С‹.")
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
                        parse_int(material_id, "РЎС‹СЂСЊС‘"),
                        parse_decimal(quantity, "РљРѕР»РёС‡РµСЃС‚РІРѕ"),
                        clean_text(unit),
                        clean_text(stage),
                        parse_decimal(waste_percent, "РџСЂРѕС†РµРЅС‚ РїРѕС‚РµСЂСЊ"),
                        clean_text(note),
                    ),
                )
        set_flash(request, "РРЅРіСЂРµРґРёРµРЅС‚ СЂРµС†РµРїС‚СѓСЂС‹ СѓСЃРїРµС€РЅРѕ РѕР±РЅРѕРІР»С‘РЅ.")
        return redirect_to(f"/tech-cards/{item['tech_card_id']}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"Р РµРґР°РєС‚РёСЂРѕРІР°С‚СЊ РёРЅРіСЂРµРґРёРµРЅС‚ #{recipe_item_id}", "action": f"/recipe-items/{recipe_item_id}/edit", "fields": recipe_item_fields(materials, form_data), "back_url": f"/tech-cards/{item['tech_card_id']}", "submit_label": "РЎРѕС…СЂР°РЅРёС‚СЊ РёР·РјРµРЅРµРЅРёСЏ", "error_message": str(exc)}, status_code=400)
