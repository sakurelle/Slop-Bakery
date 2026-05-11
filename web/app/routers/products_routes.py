from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_action, authorize_section, redirect_to, render_template, set_flash
from ..database import fetch_all, fetch_one, get_db, next_id
from ..permissions import has_action
from ..utils import clean_text, parse_bool, parse_decimal, parse_int


router = APIRouter()


def product_fields(data=None):
    data = data or {}
    return [
        {"name": "name", "label": "Наименование продукции", "type": "text", "required": True, "value": data.get("name", "")},
        {"name": "category", "label": "Категория", "type": "text", "value": data.get("category", "")},
        {"name": "unit", "label": "Единица измерения", "type": "text", "required": True, "value": data.get("unit", "piece")},
        {"name": "price", "label": "Цена", "type": "number", "required": True, "step": "0.01", "min": "0", "value": data.get("price", "")},
        {"name": "shelf_life_days", "label": "Срок годности (дней)", "type": "number", "required": True, "min": "1", "value": data.get("shelf_life_days", "")},
        {"name": "is_active", "label": "Активна", "type": "checkbox", "value": bool(data.get("is_active", True))},
    ]


@router.get("/products")
def products_list(request: Request):
    user = authorize_section(request, "products")
    if not isinstance(user, dict):
        return user
    rows = fetch_all(
        """
        SELECT product_id, name, category, unit, price, shelf_life_days, is_active
        FROM products
        ORDER BY product_id
        """
    )
    for row in rows:
        row["_detail_url"] = f"/products/{row['product_id']}"
    context = {
        "title": "Продукция",
        "subtitle": "Справочник готовой продукции.",
        "headers": [
            ("product_id", "ID"),
            ("name", "Продукция"),
            ("category", "Категория"),
            ("unit", "Ед."),
            ("price", "Цена"),
            ("shelf_life_days", "Срок годности"),
            ("is_active", "Активна"),
        ],
        "rows": rows,
    }
    if has_action(user, "products.manage"):
        context["create_url"] = "/products/new"
        context["create_label"] = "Добавить продукцию"
    return render_template(request, "table_list.html", context)


@router.get("/products/new")
def product_new_page(request: Request):
    user = authorize_action(request, "products.manage", "У вас нет прав на управление продукцией.")
    if not isinstance(user, dict):
        return user
    return render_template(
        request,
        "form.html",
        {"title": "Добавить продукцию", "action": "/products/new", "fields": product_fields(), "back_url": "/products", "submit_label": "Создать запись"},
    )


@router.post("/products/new")
def product_new(
    request: Request,
    name: str = Form(...),
    category: str = Form(""),
    unit: str = Form(...),
    price: str = Form(...),
    shelf_life_days: str = Form(...),
    is_active: str | None = Form(None),
):
    user = authorize_action(request, "products.manage", "У вас нет прав на управление продукцией.")
    if not isinstance(user, dict):
        return user

    form_data = {"name": name, "category": category, "unit": unit, "price": price, "shelf_life_days": shelf_life_days, "is_active": parse_bool(is_active)}
    try:
        product_price = parse_decimal(price, "Цена")
        shelf_life = parse_int(shelf_life_days, "Срок годности")
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            product_id = next_id(conn, "products", "product_id")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO products (product_id, name, category, unit, price, shelf_life_days, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (product_id, clean_text(name), clean_text(category), clean_text(unit), product_price, shelf_life, parse_bool(is_active)),
                )
        set_flash(request, "Продукция успешно добавлена.")
        return redirect_to("/products")
    except (PsycopgError, ValueError) as exc:
        return render_template(
            request,
            "form.html",
            {"title": "Добавить продукцию", "action": "/products/new", "fields": product_fields(form_data), "back_url": "/products", "submit_label": "Создать запись", "error_message": str(exc)},
            status_code=400,
        )


@router.get("/products/{product_id}")
def product_detail(request: Request, product_id: int):
    user = authorize_section(request, "products")
    if not isinstance(user, dict):
        return user
    product = fetch_one("SELECT * FROM products WHERE product_id = %s", (product_id,))
    if not product:
        return render_template(request, "error.html", {"title": "Продукция не найдена", "message": "Карточка продукции не найдена."}, status_code=404)
    tech_cards = fetch_all(
        """
        SELECT tech_card_id, card_number, version, status_code, effective_from, effective_to
        FROM tech_cards
        WHERE product_id = %s
        ORDER BY version DESC
        """,
        (product_id,),
    )
    return render_template(
        request,
        "detail.html",
        {
            "title": product["name"],
            "back_url": "/products",
            "edit_url": f"/products/{product_id}/edit" if has_action(user, "products.manage") else None,
            "details": [
                ("ID", product["product_id"]),
                ("Категория", product["category"]),
                ("Единица измерения", product["unit"]),
                ("Цена", product["price"]),
                ("Срок годности, дней", product["shelf_life_days"]),
                ("Создана", product["created_at"]),
                ("Активна", product["is_active"]),
            ],
            "sections": [
                {
                    "title": "Технологические карты",
                    "headers": [("tech_card_id", "ID"), ("card_number", "Номер карты"), ("version", "Версия"), ("status_code", "Статус"), ("effective_from", "Действует с"), ("effective_to", "Действует до")],
                    "rows": tech_cards,
                    "empty_message": "Для этой продукции технологические карты не найдены.",
                }
            ],
        },
    )


@router.get("/products/{product_id}/edit")
def product_edit_page(request: Request, product_id: int):
    user = authorize_action(request, "products.manage", "У вас нет прав на управление продукцией.")
    if not isinstance(user, dict):
        return user
    product = fetch_one("SELECT * FROM products WHERE product_id = %s", (product_id,))
    if not product:
        return render_template(request, "error.html", {"title": "Продукция не найдена", "message": "Карточка продукции не найдена."}, status_code=404)
    return render_template(
        request,
        "form.html",
        {"title": f"Редактировать продукцию #{product_id}", "action": f"/products/{product_id}/edit", "fields": product_fields(product), "back_url": f"/products/{product_id}", "submit_label": "Сохранить изменения"},
    )


@router.post("/products/{product_id}/edit")
def product_edit(
    request: Request,
    product_id: int,
    name: str = Form(...),
    category: str = Form(""),
    unit: str = Form(...),
    price: str = Form(...),
    shelf_life_days: str = Form(...),
    is_active: str | None = Form(None),
):
    user = authorize_action(request, "products.manage", "У вас нет прав на управление продукцией.")
    if not isinstance(user, dict):
        return user

    form_data = {"name": name, "category": category, "unit": unit, "price": price, "shelf_life_days": shelf_life_days, "is_active": parse_bool(is_active)}
    try:
        product_price = parse_decimal(price, "Цена")
        shelf_life = parse_int(shelf_life_days, "Срок годности")
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE products
                    SET name = %s,
                        category = %s,
                        unit = %s,
                        price = %s,
                        shelf_life_days = %s,
                        is_active = %s
                    WHERE product_id = %s
                    """,
                    (clean_text(name), clean_text(category), clean_text(unit), product_price, shelf_life, parse_bool(is_active), product_id),
                )
        set_flash(request, "Данные продукции успешно обновлены.")
        return redirect_to(f"/products/{product_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(
            request,
            "form.html",
            {"title": f"Редактировать продукцию #{product_id}", "action": f"/products/{product_id}/edit", "fields": product_fields(form_data), "back_url": f"/products/{product_id}", "submit_label": "Сохранить изменения", "error_message": str(exc)},
            status_code=400,
        )
