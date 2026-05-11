from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_section, redirect_to, render_template, set_flash
from ..database import fetch_all, fetch_one, get_db, next_id
from ..utils import clean_text, parse_bool, parse_decimal, parse_int


router = APIRouter()


def product_fields(data=None):
    data = data or {}
    return [
        {"name": "name", "label": "Product Name", "type": "text", "required": True, "value": data.get("name", "")},
        {"name": "category", "label": "Category", "type": "text", "value": data.get("category", "")},
        {"name": "unit", "label": "Unit", "type": "text", "required": True, "value": data.get("unit", "piece")},
        {"name": "price", "label": "Price", "type": "number", "required": True, "step": "0.01", "min": "0", "value": data.get("price", "")},
        {"name": "shelf_life_days", "label": "Shelf Life (days)", "type": "number", "required": True, "min": "1", "value": data.get("shelf_life_days", "")},
        {"name": "is_active", "label": "Active", "type": "checkbox", "value": bool(data.get("is_active", True))},
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
        "title": "Products",
        "subtitle": "Finished goods catalogue.",
        "headers": [
            ("product_id", "ID"),
            ("name", "Product"),
            ("category", "Category"),
            ("unit", "Unit"),
            ("price", "Price"),
            ("shelf_life_days", "Shelf Life"),
            ("is_active", "Active"),
        ],
        "rows": rows,
    }
    if "client" not in user.get("roles", []):
        context["create_url"] = "/products/new"
        context["create_label"] = "Add Product"
    return render_template(request, "table_list.html", context)


@router.get("/products/new")
def product_new_page(request: Request):
    user = authorize_section(request, "products")
    if not isinstance(user, dict):
        return user
    if "client" in user.get("roles", []):
        return render_template(request, "error.html", {"title": "Access denied", "message": "Clients can only view products."}, status_code=403)
    return render_template(
        request,
        "form.html",
        {"title": "Add Product", "action": "/products/new", "fields": product_fields(), "back_url": "/products", "submit_label": "Create Product"},
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
    user = authorize_section(request, "products")
    if not isinstance(user, dict):
        return user
    if "client" in user.get("roles", []):
        return render_template(request, "error.html", {"title": "Access denied", "message": "Clients can only view products."}, status_code=403)

    form_data = {"name": name, "category": category, "unit": unit, "price": price, "shelf_life_days": shelf_life_days, "is_active": parse_bool(is_active)}
    try:
        product_price = parse_decimal(price, "Price")
        shelf_life = parse_int(shelf_life_days, "Shelf Life")
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
        set_flash(request, "Product created successfully.")
        return redirect_to("/products")
    except (PsycopgError, ValueError) as exc:
        return render_template(
            request,
            "form.html",
            {"title": "Add Product", "action": "/products/new", "fields": product_fields(form_data), "back_url": "/products", "submit_label": "Create Product", "error_message": str(exc)},
            status_code=400,
        )


@router.get("/products/{product_id}")
def product_detail(request: Request, product_id: int):
    user = authorize_section(request, "products")
    if not isinstance(user, dict):
        return user
    product = fetch_one("SELECT * FROM products WHERE product_id = %s", (product_id,))
    if not product:
        return render_template(request, "error.html", {"title": "Product not found", "message": "Product record not found."}, status_code=404)
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
            "edit_url": None if "client" in user.get("roles", []) else f"/products/{product_id}/edit",
            "details": [
                ("ID", product["product_id"]),
                ("Category", product["category"]),
                ("Unit", product["unit"]),
                ("Price", product["price"]),
                ("Shelf Life Days", product["shelf_life_days"]),
                ("Created At", product["created_at"]),
                ("Active", product["is_active"]),
            ],
            "sections": [
                {
                    "title": "Tech Cards",
                    "headers": [("tech_card_id", "ID"), ("card_number", "Card Number"), ("version", "Version"), ("status_code", "Status"), ("effective_from", "Effective From"), ("effective_to", "Effective To")],
                    "rows": tech_cards,
                    "empty_message": "No tech cards linked to this product.",
                }
            ],
        },
    )


@router.get("/products/{product_id}/edit")
def product_edit_page(request: Request, product_id: int):
    user = authorize_section(request, "products")
    if not isinstance(user, dict):
        return user
    if "client" in user.get("roles", []):
        return render_template(request, "error.html", {"title": "Access denied", "message": "Clients can only view products."}, status_code=403)
    product = fetch_one("SELECT * FROM products WHERE product_id = %s", (product_id,))
    if not product:
        return render_template(request, "error.html", {"title": "Product not found", "message": "Product record not found."}, status_code=404)
    return render_template(
        request,
        "form.html",
        {"title": f"Edit Product #{product_id}", "action": f"/products/{product_id}/edit", "fields": product_fields(product), "back_url": f"/products/{product_id}", "submit_label": "Save Changes"},
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
    user = authorize_section(request, "products")
    if not isinstance(user, dict):
        return user
    if "client" in user.get("roles", []):
        return render_template(request, "error.html", {"title": "Access denied", "message": "Clients can only view products."}, status_code=403)

    form_data = {"name": name, "category": category, "unit": unit, "price": price, "shelf_life_days": shelf_life_days, "is_active": parse_bool(is_active)}
    try:
        product_price = parse_decimal(price, "Price")
        shelf_life = parse_int(shelf_life_days, "Shelf Life")
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
        set_flash(request, "Product updated successfully.")
        return redirect_to(f"/products/{product_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(
            request,
            "form.html",
            {"title": f"Edit Product #{product_id}", "action": f"/products/{product_id}/edit", "fields": product_fields(form_data), "back_url": f"/products/{product_id}", "submit_label": "Save Changes", "error_message": str(exc)},
            status_code=400,
        )
