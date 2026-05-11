from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_section, redirect_to, render_template, set_flash
from ..database import fetch_all, fetch_one, get_db, next_id
from ..utils import clean_text, parse_bool


router = APIRouter()


def customer_form_fields(data=None):
    data = data or {}
    return [
        {
            "name": "customer_type",
            "label": "Тип клиента",
            "type": "select",
            "required": True,
            "value": data.get("customer_type", "individual"),
            "options": [
                {"value": "individual", "label": "Физическое лицо"},
                {"value": "company", "label": "Компания"},
            ],
        },
        {"name": "full_name", "label": "ФИО", "type": "text", "value": data.get("full_name", "")},
        {"name": "company_name", "label": "Название компании", "type": "text", "value": data.get("company_name", "")},
        {"name": "phone", "label": "Телефон", "type": "text", "required": True, "value": data.get("phone", "")},
        {"name": "email", "label": "Email", "type": "email", "value": data.get("email", "")},
        {
            "name": "delivery_address",
            "label": "Адрес доставки",
            "type": "textarea",
            "required": True,
            "value": data.get("delivery_address", ""),
        },
        {
            "name": "is_active",
            "label": "Активен",
            "type": "checkbox",
            "value": bool(data.get("is_active", True)),
        },
    ]


@router.get("/customers")
def customers_list(request: Request):
    user = authorize_section(request, "customers")
    if not isinstance(user, dict):
        return user

    rows = fetch_all(
        """
        SELECT
            customer_id,
            customer_type,
            COALESCE(company_name, full_name) AS display_name,
            phone,
            email,
            is_active
        FROM customers
        ORDER BY customer_id
        """
    )
    for row in rows:
        row["_detail_url"] = f"/customers/{row['customer_id']}"
    return render_template(
        request,
        "table_list.html",
        {
            "title": "Клиенты",
            "subtitle": "Реестр клиентов с признаком активности.",
            "headers": [
                ("customer_id", "ID"),
                ("customer_type", "Тип"),
                ("display_name", "Наименование"),
                ("phone", "Телефон"),
                ("email", "Email"),
                ("is_active", "Активен"),
            ],
            "rows": rows,
            "create_url": "/customers/new",
            "create_label": "Добавить клиента",
        },
    )


@router.get("/customers/new")
def customer_create_page(request: Request):
    user = authorize_section(request, "customers")
    if not isinstance(user, dict):
        return user
    return render_template(
        request,
        "form.html",
        {
            "title": "Добавить клиента",
            "action": "/customers/new",
            "fields": customer_form_fields(),
            "back_url": "/customers",
            "submit_label": "Создать клиента",
        },
    )


@router.post("/customers/new")
def customer_create(
    request: Request,
    customer_type: str = Form(...),
    full_name: str = Form(""),
    company_name: str = Form(""),
    phone: str = Form(...),
    email: str = Form(""),
    delivery_address: str = Form(...),
    is_active: str | None = Form(None),
):
    user = authorize_section(request, "customers")
    if not isinstance(user, dict):
        return user

    form_data = {
        "customer_type": customer_type,
        "full_name": full_name,
        "company_name": company_name,
        "phone": phone,
        "email": email,
        "delivery_address": delivery_address,
        "is_active": parse_bool(is_active),
    }

    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            customer_id = next_id(conn, "customers", "customer_id")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO customers (
                        customer_id,
                        customer_type,
                        full_name,
                        company_name,
                        phone,
                        email,
                        delivery_address,
                        is_active
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        customer_id,
                        clean_text(customer_type),
                        clean_text(full_name),
                        clean_text(company_name),
                        clean_text(phone),
                        clean_text(email),
                        clean_text(delivery_address),
                        parse_bool(is_active),
                    ),
                )
        set_flash(request, "Клиент успешно создан.")
        return redirect_to("/customers")
    except (PsycopgError, ValueError) as exc:
        return render_template(
            request,
            "form.html",
            {
                "title": "Добавить клиента",
                "action": "/customers/new",
                "fields": customer_form_fields(form_data),
                "back_url": "/customers",
                "submit_label": "Создать клиента",
                "error_message": str(exc),
            },
            status_code=400,
        )


@router.get("/customers/{customer_id}")
def customer_detail(request: Request, customer_id: int):
    user = authorize_section(request, "customers")
    if not isinstance(user, dict):
        return user

    customer = fetch_one("SELECT * FROM customers WHERE customer_id = %s", (customer_id,))
    if not customer:
        return render_template(
            request,
            "error.html",
            {"title": "Клиент не найден", "message": "Запрошенный клиент не существует."},
            status_code=404,
        )

    orders = fetch_all(
        """
        SELECT order_number, order_date, status_code, planned_shipment_date
        FROM customer_orders
        WHERE customer_id = %s
        ORDER BY order_date DESC
        """,
        (customer_id,),
    )
    return render_template(
        request,
        "detail.html",
        {
            "title": f"Клиент #{customer_id}",
            "back_url": "/customers",
            "edit_url": f"/customers/{customer_id}/edit",
            "extra_forms": [
                {
                    "action": f"/customers/{customer_id}/deactivate",
                    "label": "Деактивировать",
                    "class": "btn-outline-danger",
                }
            ] if customer["is_active"] else [],
            "details": [
                ("ID", customer["customer_id"]),
                ("Тип", customer["customer_type"]),
                ("ФИО", customer["full_name"]),
                ("Название компании", customer["company_name"]),
                ("Телефон", customer["phone"]),
                ("Email", customer["email"]),
                ("Адрес доставки", customer["delivery_address"]),
                ("Создан", customer["created_at"]),
                ("Активен", customer["is_active"]),
            ],
            "sections": [
                {
                    "title": "Заказы",
                    "headers": [("order_number", "Заказ"), ("order_date", "Дата"), ("status_code", "Статус"), ("planned_shipment_date", "Плановая отгрузка")],
                    "rows": orders,
                    "empty_message": "У этого клиента нет заказов.",
                }
            ],
        },
    )


@router.get("/customers/{customer_id}/edit")
def customer_edit_page(request: Request, customer_id: int):
    user = authorize_section(request, "customers")
    if not isinstance(user, dict):
        return user
    customer = fetch_one("SELECT * FROM customers WHERE customer_id = %s", (customer_id,))
    if not customer:
        return render_template(request, "error.html", {"title": "Клиент не найден", "message": "Карточка клиента не найдена."}, status_code=404)
    return render_template(
        request,
        "form.html",
        {
            "title": f"Редактировать клиента #{customer_id}",
            "action": f"/customers/{customer_id}/edit",
            "fields": customer_form_fields(customer),
            "back_url": f"/customers/{customer_id}",
            "submit_label": "Сохранить изменения",
        },
    )


@router.post("/customers/{customer_id}/edit")
def customer_edit(
    request: Request,
    customer_id: int,
    customer_type: str = Form(...),
    full_name: str = Form(""),
    company_name: str = Form(""),
    phone: str = Form(...),
    email: str = Form(""),
    delivery_address: str = Form(...),
    is_active: str | None = Form(None),
):
    user = authorize_section(request, "customers")
    if not isinstance(user, dict):
        return user

    form_data = {
        "customer_type": customer_type,
        "full_name": full_name,
        "company_name": company_name,
        "phone": phone,
        "email": email,
        "delivery_address": delivery_address,
        "is_active": parse_bool(is_active),
    }

    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE customers
                    SET
                        customer_type = %s,
                        full_name = %s,
                        company_name = %s,
                        phone = %s,
                        email = %s,
                        delivery_address = %s,
                        is_active = %s
                    WHERE customer_id = %s
                    """,
                    (
                        clean_text(customer_type),
                        clean_text(full_name),
                        clean_text(company_name),
                        clean_text(phone),
                        clean_text(email),
                        clean_text(delivery_address),
                        parse_bool(is_active),
                        customer_id,
                    ),
                )
        set_flash(request, "Данные клиента успешно обновлены.")
        return redirect_to(f"/customers/{customer_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(
            request,
            "form.html",
            {
                "title": f"Редактировать клиента #{customer_id}",
                "action": f"/customers/{customer_id}/edit",
                "fields": customer_form_fields(form_data),
                "back_url": f"/customers/{customer_id}",
                "submit_label": "Сохранить изменения",
                "error_message": str(exc),
            },
            status_code=400,
        )


@router.post("/customers/{customer_id}/deactivate")
def customer_deactivate(request: Request, customer_id: int):
    user = authorize_section(request, "customers")
    if not isinstance(user, dict):
        return user
    with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE customers SET is_active = FALSE WHERE customer_id = %s", (customer_id,))
    set_flash(request, "Клиент деактивирован.", "warning")
    return redirect_to(f"/customers/{customer_id}")
