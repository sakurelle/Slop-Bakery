from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_action, authorize_section, render_template, redirect_to, set_flash
from ..database import fetch_all, fetch_one, get_db, next_id
from ..permissions import has_action
from ..utils import build_options, clean_text, parse_bool, parse_decimal, parse_int


router = APIRouter()


def supplier_fields(data=None):
    data = data or {}
    return [
        {"name": "company_name", "label": "Название компании", "type": "text", "required": True, "value": data.get("company_name", "")},
        {"name": "contact_person", "label": "Контактное лицо", "type": "text", "value": data.get("contact_person", "")},
        {"name": "phone", "label": "Телефон", "type": "text", "required": True, "value": data.get("phone", "")},
        {"name": "email", "label": "Email", "type": "email", "value": data.get("email", "")},
        {"name": "address", "label": "Адрес", "type": "textarea", "value": data.get("address", "")},
        {"name": "is_active", "label": "Активен", "type": "checkbox", "value": bool(data.get("is_active", True))},
    ]


def supplier_material_fields(materials, data=None):
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
        {"name": "purchase_price", "label": "Закупочная цена", "type": "number", "step": "0.01", "min": "0", "value": data.get("purchase_price", "")},
        {"name": "lead_time_days", "label": "Срок поставки, дней", "type": "number", "min": "0", "value": data.get("lead_time_days", "")},
        {"name": "is_active", "label": "Активно", "type": "checkbox", "value": bool(data.get("is_active", True))},
    ]


def get_material_options():
    return fetch_all("SELECT material_id, name FROM raw_materials WHERE is_active = TRUE ORDER BY name")


def fetch_supplier(supplier_id: int):
    return fetch_one("SELECT * FROM suppliers WHERE supplier_id = %s", (supplier_id,))


def fetch_supplier_material(supplier_material_id: int):
    return fetch_one(
        """
        SELECT sm.*, rm.name AS material_name
        FROM supplier_materials AS sm
        JOIN raw_materials AS rm ON rm.material_id = sm.material_id
        WHERE sm.supplier_material_id = %s
        """,
        (supplier_material_id,),
    )


@router.get("/suppliers")
def suppliers_list(request: Request):
    user = authorize_section(request, "suppliers")
    if not isinstance(user, dict):
        return user
    rows = fetch_all("SELECT supplier_id, company_name, contact_person, phone, email, is_active FROM suppliers ORDER BY supplier_id")
    for row in rows:
        row["_detail_url"] = f"/suppliers/{row['supplier_id']}"
    return render_template(
        request,
        "table_list.html",
        {
            "title": "Поставщики",
            "subtitle": "Поставщики и их контактные данные.",
            "headers": [
                ("supplier_id", "ID"),
                ("company_name", "Компания"),
                ("contact_person", "Контакт"),
                ("phone", "Телефон"),
                ("email", "Email"),
                ("is_active", "Активен"),
            ],
            "rows": rows,
            "create_url": "/suppliers/new",
            "create_label": "Добавить поставщика",
        },
    )


@router.get("/suppliers/new")
def supplier_new_page(request: Request):
    user = authorize_section(request, "suppliers")
    if not isinstance(user, dict):
        return user
    return render_template(
        request,
        "form.html",
        {
            "title": "Добавить поставщика",
            "action": "/suppliers/new",
            "fields": supplier_fields(),
            "back_url": "/suppliers",
            "submit_label": "Создать поставщика",
        },
    )


@router.post("/suppliers/new")
def supplier_new(
    request: Request,
    company_name: str = Form(...),
    contact_person: str = Form(""),
    phone: str = Form(...),
    email: str = Form(""),
    address: str = Form(""),
    is_active: str | None = Form(None),
):
    user = authorize_section(request, "suppliers")
    if not isinstance(user, dict):
        return user
    form_data = {
        "company_name": company_name,
        "contact_person": contact_person,
        "phone": phone,
        "email": email,
        "address": address,
        "is_active": parse_bool(is_active),
    }
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            supplier_id = next_id(conn, "suppliers", "supplier_id")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO suppliers (
                        supplier_id, company_name, contact_person, phone, email, address, is_active
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        supplier_id,
                        clean_text(company_name),
                        clean_text(contact_person),
                        clean_text(phone),
                        clean_text(email),
                        clean_text(address),
                        parse_bool(is_active),
                    ),
                )
        set_flash(request, "Поставщик успешно создан.")
        return redirect_to("/suppliers")
    except (PsycopgError, ValueError) as exc:
        return render_template(
            request,
            "form.html",
            {
                "title": "Добавить поставщика",
                "action": "/suppliers/new",
                "fields": supplier_fields(form_data),
                "back_url": "/suppliers",
                "submit_label": "Создать поставщика",
                "error_message": str(exc),
            },
            status_code=400,
        )


@router.get("/suppliers/{supplier_id}")
def supplier_detail(request: Request, supplier_id: int):
    user = authorize_section(request, "suppliers")
    if not isinstance(user, dict):
        return user
    supplier = fetch_supplier(supplier_id)
    if not supplier:
        return render_template(request, "error.html", {"title": "Поставщик не найден", "message": "Карточка поставщика не найдена."}, status_code=404)

    materials = fetch_all(
        """
        SELECT
            sm.supplier_material_id,
            rm.name,
            sm.purchase_price,
            sm.lead_time_days,
            sm.is_active
        FROM supplier_materials AS sm
        JOIN raw_materials AS rm ON rm.material_id = sm.material_id
        WHERE sm.supplier_id = %s
        ORDER BY rm.name
        """,
        (supplier_id,),
    )
    if has_action(user, "suppliers.manage_materials"):
        for row in materials:
            row["_detail_url"] = f"/suppliers/{supplier_id}/materials/{row['supplier_material_id']}/edit"
            row["_row_forms"] = [
                {
                    "action": f"/suppliers/{supplier_id}/materials/{row['supplier_material_id']}/deactivate",
                    "label": "Отключить",
                    "class": "btn-outline-warning",
                }
            ] if row["is_active"] else []

    extra_actions = []
    if has_action(user, "suppliers.manage_materials"):
        extra_actions.append({"label": "Добавить поставляемое сырьё", "url": f"/suppliers/{supplier_id}/materials/new"})

    return render_template(
        request,
        "detail.html",
        {
            "title": supplier["company_name"],
            "back_url": "/suppliers",
            "edit_url": f"/suppliers/{supplier_id}/edit",
            "extra_actions": extra_actions,
            "details": [
                ("ID", supplier["supplier_id"]),
                ("Компания", supplier["company_name"]),
                ("Контактное лицо", supplier["contact_person"]),
                ("Телефон", supplier["phone"]),
                ("Email", supplier["email"]),
                ("Адрес", supplier["address"]),
                ("Создан", supplier["created_at"]),
                ("Активен", supplier["is_active"]),
            ],
            "sections": [
                {
                    "title": "Поставляемое сырьё",
                    "headers": [("name", "Сырьё"), ("purchase_price", "Цена"), ("lead_time_days", "Срок поставки"), ("is_active", "Активно")],
                    "rows": materials,
                    "empty_message": "Для этого поставщика ещё не задано поставляемое сырьё.",
                }
            ],
        },
    )


@router.get("/suppliers/{supplier_id}/edit")
def supplier_edit_page(request: Request, supplier_id: int):
    user = authorize_section(request, "suppliers")
    if not isinstance(user, dict):
        return user
    supplier = fetch_supplier(supplier_id)
    if not supplier:
        return render_template(request, "error.html", {"title": "Поставщик не найден", "message": "Карточка поставщика не найдена."}, status_code=404)
    return render_template(
        request,
        "form.html",
        {
            "title": f"Редактировать поставщика #{supplier_id}",
            "action": f"/suppliers/{supplier_id}/edit",
            "fields": supplier_fields(supplier),
            "back_url": f"/suppliers/{supplier_id}",
            "submit_label": "Сохранить изменения",
        },
    )


@router.post("/suppliers/{supplier_id}/edit")
def supplier_edit(
    request: Request,
    supplier_id: int,
    company_name: str = Form(...),
    contact_person: str = Form(""),
    phone: str = Form(...),
    email: str = Form(""),
    address: str = Form(""),
    is_active: str | None = Form(None),
):
    user = authorize_section(request, "suppliers")
    if not isinstance(user, dict):
        return user
    form_data = {
        "company_name": company_name,
        "contact_person": contact_person,
        "phone": phone,
        "email": email,
        "address": address,
        "is_active": parse_bool(is_active),
    }
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE suppliers
                    SET company_name = %s,
                        contact_person = %s,
                        phone = %s,
                        email = %s,
                        address = %s,
                        is_active = %s
                    WHERE supplier_id = %s
                    """,
                    (
                        clean_text(company_name),
                        clean_text(contact_person),
                        clean_text(phone),
                        clean_text(email),
                        clean_text(address),
                        parse_bool(is_active),
                        supplier_id,
                    ),
                )
        set_flash(request, "Данные поставщика успешно обновлены.")
        return redirect_to(f"/suppliers/{supplier_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(
            request,
            "form.html",
            {
                "title": f"Редактировать поставщика #{supplier_id}",
                "action": f"/suppliers/{supplier_id}/edit",
                "fields": supplier_fields(form_data),
                "back_url": f"/suppliers/{supplier_id}",
                "submit_label": "Сохранить изменения",
                "error_message": str(exc),
            },
            status_code=400,
        )


@router.get("/suppliers/{supplier_id}/materials/new")
def supplier_material_new_page(request: Request, supplier_id: int):
    user = authorize_action(request, "suppliers.manage_materials", "У вас нет прав на управление поставляемым сырьём.")
    if not isinstance(user, dict):
        return user
    supplier = fetch_supplier(supplier_id)
    if not supplier:
        return render_template(request, "error.html", {"title": "Поставщик не найден", "message": "Карточка поставщика не найдена."}, status_code=404)
    return render_template(
        request,
        "form.html",
        {
            "title": f"Добавить поставляемое сырьё для {supplier['company_name']}",
            "action": f"/suppliers/{supplier_id}/materials/new",
            "fields": supplier_material_fields(get_material_options()),
            "back_url": f"/suppliers/{supplier_id}",
            "submit_label": "Сохранить связь",
        },
    )


@router.post("/suppliers/{supplier_id}/materials/new")
def supplier_material_new(
    request: Request,
    supplier_id: int,
    material_id: str = Form(...),
    purchase_price: str = Form(""),
    lead_time_days: str = Form(""),
    is_active: str | None = Form(None),
):
    user = authorize_action(request, "suppliers.manage_materials", "У вас нет прав на управление поставляемым сырьём.")
    if not isinstance(user, dict):
        return user
    supplier = fetch_supplier(supplier_id)
    if not supplier:
        return render_template(request, "error.html", {"title": "Поставщик не найден", "message": "Карточка поставщика не найдена."}, status_code=404)
    materials = get_material_options()
    form_data = {
        "material_id": material_id,
        "purchase_price": purchase_price,
        "lead_time_days": lead_time_days,
        "is_active": parse_bool(is_active),
    }
    try:
        material_id_value = parse_int(material_id, "Сырьё")
        purchase_price_value = parse_decimal(purchase_price, "Закупочная цена", allow_none=True)
        lead_time_value = parse_int(lead_time_days, "Срок поставки", allow_none=True)
        if purchase_price_value is not None and purchase_price_value < 0:
            raise ValueError("Закупочная цена не может быть отрицательной.")
        if lead_time_value is not None and lead_time_value < 0:
            raise ValueError("Срок поставки не может быть отрицательным.")

        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM raw_materials WHERE material_id = %s", (material_id_value,))
                if not cur.fetchone():
                    raise ValueError("Выбранное сырьё не существует.")

                cur.execute(
                    """
                    SELECT supplier_material_id
                    FROM supplier_materials
                    WHERE supplier_id = %s
                      AND material_id = %s
                    """,
                    (supplier_id, material_id_value),
                )
                existing = cur.fetchone()

                if existing:
                    cur.execute(
                        """
                        UPDATE supplier_materials
                        SET purchase_price = %s,
                            lead_time_days = %s,
                            is_active = %s
                        WHERE supplier_material_id = %s
                        """,
                        (
                            purchase_price_value,
                            lead_time_value,
                            parse_bool(is_active),
                            existing["supplier_material_id"],
                        ),
                    )
                    set_flash(request, "Поставляемое сырьё уже закреплено, данные обновлены.")
                else:
                    supplier_material_id = next_id(conn, "supplier_materials", "supplier_material_id")
                    cur.execute(
                        """
                        INSERT INTO supplier_materials (
                            supplier_material_id, supplier_id, material_id, purchase_price, lead_time_days, is_active
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            supplier_material_id,
                            supplier_id,
                            material_id_value,
                            purchase_price_value,
                            lead_time_value,
                            parse_bool(is_active),
                        ),
                    )
                    set_flash(request, "Поставляемое сырьё успешно добавлено.")
        return redirect_to(f"/suppliers/{supplier_id}")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "Не удалось сохранить поставляемое сырьё."

    return render_template(
        request,
        "form.html",
        {
            "title": f"Добавить поставляемое сырьё для {supplier['company_name']}",
            "action": f"/suppliers/{supplier_id}/materials/new",
            "fields": supplier_material_fields(materials, form_data),
            "back_url": f"/suppliers/{supplier_id}",
            "submit_label": "Сохранить связь",
            "error_message": error_message,
        },
        status_code=400,
    )


@router.get("/suppliers/{supplier_id}/materials/{supplier_material_id}/edit")
def supplier_material_edit_page(request: Request, supplier_id: int, supplier_material_id: int):
    user = authorize_action(request, "suppliers.manage_materials", "У вас нет прав на управление поставляемым сырьём.")
    if not isinstance(user, dict):
        return user
    supplier = fetch_supplier(supplier_id)
    supplier_material = fetch_supplier_material(supplier_material_id)
    if not supplier or not supplier_material or supplier_material["supplier_id"] != supplier_id:
        return render_template(request, "error.html", {"title": "Связь не найдена", "message": "Запись поставляемого сырья не найдена."}, status_code=404)
    return render_template(
        request,
        "form.html",
        {
            "title": f"Редактировать поставляемое сырьё для {supplier['company_name']}",
            "action": f"/suppliers/{supplier_id}/materials/{supplier_material_id}/edit",
            "fields": supplier_material_fields(get_material_options(), supplier_material),
            "back_url": f"/suppliers/{supplier_id}",
            "submit_label": "Сохранить изменения",
        },
    )


@router.post("/suppliers/{supplier_id}/materials/{supplier_material_id}/edit")
def supplier_material_edit(
    request: Request,
    supplier_id: int,
    supplier_material_id: int,
    material_id: str = Form(...),
    purchase_price: str = Form(""),
    lead_time_days: str = Form(""),
    is_active: str | None = Form(None),
):
    user = authorize_action(request, "suppliers.manage_materials", "У вас нет прав на управление поставляемым сырьём.")
    if not isinstance(user, dict):
        return user
    supplier = fetch_supplier(supplier_id)
    supplier_material = fetch_supplier_material(supplier_material_id)
    if not supplier or not supplier_material or supplier_material["supplier_id"] != supplier_id:
        return render_template(request, "error.html", {"title": "Связь не найдена", "message": "Запись поставляемого сырья не найдена."}, status_code=404)

    materials = get_material_options()
    form_data = {
        "material_id": material_id,
        "purchase_price": purchase_price,
        "lead_time_days": lead_time_days,
        "is_active": parse_bool(is_active),
    }
    try:
        material_id_value = parse_int(material_id, "Сырьё")
        purchase_price_value = parse_decimal(purchase_price, "Закупочная цена", allow_none=True)
        lead_time_value = parse_int(lead_time_days, "Срок поставки", allow_none=True)
        if purchase_price_value is not None and purchase_price_value < 0:
            raise ValueError("Закупочная цена не может быть отрицательной.")
        if lead_time_value is not None and lead_time_value < 0:
            raise ValueError("Срок поставки не может быть отрицательным.")

        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT supplier_material_id
                    FROM supplier_materials
                    WHERE supplier_id = %s
                      AND material_id = %s
                      AND supplier_material_id <> %s
                    """,
                    (supplier_id, material_id_value, supplier_material_id),
                )
                existing = cur.fetchone()
                if existing:
                    raise ValueError("Поставляемое сырьё уже закреплено за этим поставщиком.")

                cur.execute(
                    """
                    UPDATE supplier_materials
                    SET material_id = %s,
                        purchase_price = %s,
                        lead_time_days = %s,
                        is_active = %s
                    WHERE supplier_material_id = %s
                    """,
                    (
                        material_id_value,
                        purchase_price_value,
                        lead_time_value,
                        parse_bool(is_active),
                        supplier_material_id,
                    ),
                )
        set_flash(request, "Связь поставщик–сырьё успешно обновлена.")
        return redirect_to(f"/suppliers/{supplier_id}")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "Не удалось обновить поставляемое сырьё."

    return render_template(
        request,
        "form.html",
        {
            "title": f"Редактировать поставляемое сырьё для {supplier['company_name']}",
            "action": f"/suppliers/{supplier_id}/materials/{supplier_material_id}/edit",
            "fields": supplier_material_fields(materials, form_data),
            "back_url": f"/suppliers/{supplier_id}",
            "submit_label": "Сохранить изменения",
            "error_message": error_message,
        },
        status_code=400,
    )


@router.post("/suppliers/{supplier_id}/materials/{supplier_material_id}/deactivate")
def supplier_material_deactivate(request: Request, supplier_id: int, supplier_material_id: int):
    user = authorize_action(request, "suppliers.manage_materials", "У вас нет прав на управление поставляемым сырьём.")
    if not isinstance(user, dict):
        return user
    supplier_material = fetch_supplier_material(supplier_material_id)
    if not supplier_material or supplier_material["supplier_id"] != supplier_id:
        return render_template(request, "error.html", {"title": "Связь не найдена", "message": "Запись поставляемого сырья не найдена."}, status_code=404)
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE supplier_materials SET is_active = FALSE WHERE supplier_material_id = %s",
                    (supplier_material_id,),
                )
        set_flash(request, "Поставляемое сырьё отключено.")
    except PsycopgError:
        set_flash(request, "Не удалось отключить поставляемое сырьё.", "danger")
    return redirect_to(f"/suppliers/{supplier_id}")
