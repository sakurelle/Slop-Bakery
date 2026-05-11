from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_section, redirect_to, render_template, set_flash
from ..database import fetch_all, fetch_one, get_db, next_id
from ..utils import clean_text, parse_bool


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
    supplier = fetch_one("SELECT * FROM suppliers WHERE supplier_id = %s", (supplier_id,))
    if not supplier:
        return render_template(request, "error.html", {"title": "Поставщик не найден", "message": "Карточка поставщика не найдена."}, status_code=404)
    materials = fetch_all(
        """
        SELECT rm.name, sm.purchase_price, sm.lead_time_days, sm.is_active
        FROM supplier_materials AS sm
        JOIN raw_materials AS rm ON rm.material_id = sm.material_id
        WHERE sm.supplier_id = %s
        ORDER BY rm.name
        """,
        (supplier_id,),
    )
    return render_template(
        request,
        "detail.html",
        {
            "title": supplier["company_name"],
            "back_url": "/suppliers",
            "edit_url": f"/suppliers/{supplier_id}/edit",
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
                    "empty_message": "Для этого поставщика сырьё не задано.",
                }
            ],
        },
    )


@router.get("/suppliers/{supplier_id}/edit")
def supplier_edit_page(request: Request, supplier_id: int):
    user = authorize_section(request, "suppliers")
    if not isinstance(user, dict):
        return user
    supplier = fetch_one("SELECT * FROM suppliers WHERE supplier_id = %s", (supplier_id,))
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
