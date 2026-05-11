from datetime import date, timedelta

from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_action, authorize_section, forbidden_response, redirect_to, render_template, set_flash
from ..database import fetch_all, fetch_one, get_db, next_id
from ..permissions import has_action
from ..utils import build_options, clean_text, parse_bool, parse_date, parse_decimal, parse_int


router = APIRouter()

DELIVERY_STOCK_STATUSES = {"received", "accepted"}
DELIVERY_MUTABLE_STATUSES = {"planned", "received"}


def material_fields(data=None):
    data = data or {}
    return [
        {"name": "name", "label": "Наименование сырья", "type": "text", "required": True, "value": data.get("name", "")},
        {"name": "unit", "label": "Единица измерения", "type": "text", "required": True, "value": data.get("unit", "kg")},
        {"name": "min_stock_qty", "label": "Минимальный остаток", "type": "number", "required": True, "step": "0.001", "min": "0", "value": data.get("min_stock_qty", "0")},
        {"name": "shelf_life_days", "label": "Срок годности (дней)", "type": "number", "min": "1", "value": data.get("shelf_life_days", "")},
        {"name": "storage_conditions", "label": "Условия хранения", "type": "textarea", "value": data.get("storage_conditions", "")},
        {"name": "is_active", "label": "Активно", "type": "checkbox", "value": bool(data.get("is_active", True))},
    ]


def delivery_fields(suppliers, statuses, data=None):
    data = data or {}
    return [
        {
            "name": "supplier_id",
            "label": "Поставщик",
            "type": "select",
            "required": True,
            "value": data.get("supplier_id", ""),
            "options": build_options(suppliers, "supplier_id", "company_name"),
        },
        {"name": "delivery_date", "label": "Дата поставки", "type": "date", "required": True, "value": data.get("delivery_date", date.today().isoformat())},
        {
            "name": "status_code",
            "label": "Статус",
            "type": "select",
            "required": True,
            "value": data.get("status_code", "planned"),
            "options": build_options(statuses, "status_code", "name"),
        },
        {"name": "document_ref", "label": "Документ", "type": "text", "value": data.get("document_ref", "")},
        {"name": "total_amount", "label": "Общая сумма", "type": "number", "step": "0.01", "min": "0", "value": data.get("total_amount", "0")},
        {"name": "note", "label": "Примечание", "type": "textarea", "value": data.get("note", "")},
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
        {"name": "unit_price", "label": "Цена за единицу", "type": "number", "required": True, "step": "0.01", "min": "0", "value": data.get("unit_price", "")},
        {"name": "batch_number", "label": "Номер партии", "type": "text", "value": data.get("batch_number", "")},
        {"name": "expiry_date", "label": "Срок годности", "type": "date", "required": True, "value": data.get("expiry_date", "")},
    ]


def delivery_status_fields(statuses, current_status):
    return [
        {
            "name": "status_code",
            "label": "Статус",
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


def sync_delivery_stock(conn, delivery_id: int) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT status_code FROM raw_material_deliveries WHERE delivery_id = %s", (delivery_id,))
        delivery = cur.fetchone()
        if not delivery:
            raise ValueError("Поставка не найдена.")
        if delivery["status_code"] not in DELIVERY_STOCK_STATUSES:
            raise ValueError("Остаток сырья можно формировать только для полученной или принятой поставки.")

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
        "title": "Сырьё",
        "subtitle": "Справочник сырья с отображением текущих остатков.",
        "headers": [
            ("material_id", "ID"),
            ("name", "Сырьё"),
            ("unit", "Ед."),
            ("min_stock_qty", "Мин. остаток"),
            ("quantity_on_hand", "Текущий остаток"),
            ("shelf_life_days", "Срок годности"),
            ("is_active", "Активно"),
        ],
        "rows": rows,
    }
    if has_action(user, "materials.manage"):
        context["create_url"] = "/materials/new"
        context["create_label"] = "Добавить сырьё"
    return render_template(request, "table_list.html", context)


@router.get("/materials/new")
def material_new_page(request: Request):
    user = authorize_action(request, "materials.manage", "У вас нет прав на управление сырьём.")
    if not isinstance(user, dict):
        return user
    return render_template(request, "form.html", {"title": "Добавить сырьё", "action": "/materials/new", "fields": material_fields(), "back_url": "/materials", "submit_label": "Создать запись"})


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
    user = authorize_action(request, "materials.manage", "У вас нет прав на управление сырьём.")
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
                        parse_decimal(min_stock_qty, "Минимальный остаток"),
                        parse_int(shelf_life_days, "Срок годности", allow_none=True),
                        clean_text(storage_conditions),
                        parse_bool(is_active),
                    ),
                )
        set_flash(request, "Сырьё успешно добавлено.")
        return redirect_to("/materials")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": "Добавить сырьё", "action": "/materials/new", "fields": material_fields(form_data), "back_url": "/materials", "submit_label": "Создать запись", "error_message": str(exc)}, status_code=400)


@router.get("/materials/{material_id}")
def material_detail(request: Request, material_id: int):
    user = authorize_section(request, "materials")
    if not isinstance(user, dict):
        return user
    material = fetch_one("SELECT * FROM raw_materials WHERE material_id = %s", (material_id,))
    if not material:
        return render_template(request, "error.html", {"title": "Сырьё не найдено", "message": "Карточка сырья не найдена."}, status_code=404)
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
                ("Единица измерения", material["unit"]),
                ("Минимальный остаток", material["min_stock_qty"]),
                ("Срок годности, дней", material["shelf_life_days"]),
                ("Условия хранения", material["storage_conditions"]),
                ("Активно", material["is_active"]),
            ],
            "sections": [
                {
                    "title": "Партии на складе",
                    "headers": [("batch_number", "Партия"), ("quantity_current", "Количество"), ("expiry_date", "Срок годности"), ("updated_at", "Обновлено")],
                    "rows": stock_rows,
                    "empty_message": "Для этого сырья складских партий нет.",
                }
            ],
        },
    )


@router.get("/materials/{material_id}/edit")
def material_edit_page(request: Request, material_id: int):
    user = authorize_action(request, "materials.manage", "У вас нет прав на управление сырьём.")
    if not isinstance(user, dict):
        return user
    material = fetch_one("SELECT * FROM raw_materials WHERE material_id = %s", (material_id,))
    if not material:
        return render_template(request, "error.html", {"title": "Сырьё не найдено", "message": "Карточка сырья не найдена."}, status_code=404)
    return render_template(request, "form.html", {"title": f"Редактировать сырьё #{material_id}", "action": f"/materials/{material_id}/edit", "fields": material_fields(material), "back_url": f"/materials/{material_id}", "submit_label": "Сохранить изменения"})


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
    user = authorize_action(request, "materials.manage", "У вас нет прав на управление сырьём.")
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
                        parse_decimal(min_stock_qty, "Минимальный остаток"),
                        parse_int(shelf_life_days, "Срок годности", allow_none=True),
                        clean_text(storage_conditions),
                        parse_bool(is_active),
                        material_id,
                    ),
                )
        set_flash(request, "Данные по сырью успешно обновлены.")
        return redirect_to(f"/materials/{material_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"Редактировать сырьё #{material_id}", "action": f"/materials/{material_id}/edit", "fields": material_fields(form_data), "back_url": f"/materials/{material_id}", "submit_label": "Сохранить изменения", "error_message": str(exc)}, status_code=400)


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
        "title": "Поставки сырья",
        "subtitle": "Входящие поставки от поставщиков.",
        "headers": [
            ("delivery_id", "ID"),
            ("delivery_number", "Номер поставки"),
            ("company_name", "Поставщик"),
            ("delivery_date", "Дата"),
            ("status_code", "Статус"),
            ("total_amount", "Сумма"),
        ],
        "rows": rows,
    }
    if has_action(user, "deliveries.create"):
        context["create_url"] = "/deliveries/new"
        context["create_label"] = "Создать поставку"
    return render_template(request, "table_list.html", context)


@router.get("/deliveries/new")
def delivery_new_page(request: Request):
    user = authorize_action(request, "deliveries.create", "У вас нет прав на создание поставок.")
    if not isinstance(user, dict):
        return user
    suppliers = fetch_all("SELECT supplier_id, company_name FROM suppliers WHERE is_active = TRUE ORDER BY company_name")
    statuses = fetch_all("SELECT status_code, name FROM delivery_statuses ORDER BY name")
    return render_template(request, "form.html", {"title": "Создать поставку", "action": "/deliveries/new", "fields": delivery_fields(suppliers, statuses), "back_url": "/deliveries", "submit_label": "Создать поставку"})


@router.post("/deliveries/new")
def delivery_new(
    request: Request,
    supplier_id: str = Form(...),
    delivery_date: str = Form(...),
    status_code: str = Form(...),
    document_ref: str = Form(""),
    total_amount: str = Form("0"),
    note: str = Form(""),
):
    user = authorize_action(request, "deliveries.create", "У вас нет прав на создание поставок.")
    if not isinstance(user, dict):
        return user
    suppliers = fetch_all("SELECT supplier_id, company_name FROM suppliers WHERE is_active = TRUE ORDER BY company_name")
    statuses = fetch_all("SELECT status_code, name FROM delivery_statuses ORDER BY name")
    form_data = {"supplier_id": supplier_id, "delivery_date": delivery_date, "status_code": status_code, "document_ref": document_ref, "total_amount": total_amount, "note": note}
    try:
        delivery_status = clean_text(status_code)
        if delivery_status not in {"planned", "received", "accepted", "rejected", "cancelled"}:
            raise ValueError("Недопустимый статус поставки.")
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
                        parse_int(supplier_id, "Поставщик"),
                        delivery_number,
                        parse_date(delivery_date, "Дата поставки"),
                        delivery_status,
                        user["user_id"],
                        clean_text(document_ref),
                        parse_decimal(total_amount, "Общая сумма"),
                        clean_text(note),
                    ),
                )
        set_flash(request, "Поставка создана. Теперь можно добавить её позиции.")
        return redirect_to(f"/deliveries/{delivery_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": "Создать поставку", "action": "/deliveries/new", "fields": delivery_fields(suppliers, statuses, form_data), "back_url": "/deliveries", "submit_label": "Создать поставку", "error_message": str(exc)}, status_code=400)


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
    extra_actions = []
    if has_action(user, "deliveries.add_item") and delivery["status_code"] in DELIVERY_MUTABLE_STATUSES:
        extra_actions.append({"label": "Добавить позицию", "url": f"/deliveries/{delivery_id}/items/new"})
    if has_action(user, "deliveries.change_status"):
        extra_actions.append({"label": "Изменить статус", "url": f"/deliveries/{delivery_id}/status"})
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
                }
            ],
        },
    )


@router.get("/deliveries/{delivery_id}/items/new")
def delivery_item_new_page(request: Request, delivery_id: int):
    user = authorize_action(request, "deliveries.add_item", "У вас нет прав на добавление позиций поставки.")
    if not isinstance(user, dict):
        return user
    delivery = fetch_delivery_for_user(delivery_id)
    if not delivery:
        return render_template(request, "error.html", {"title": "Поставка не найдена", "message": "Карточка поставки не найдена."}, status_code=404)
    if delivery["status_code"] not in DELIVERY_MUTABLE_STATUSES:
        return forbidden_response(request, "Нельзя добавлять позиции в поставку с этим статусом.")
    materials = fetch_all("SELECT material_id, name FROM raw_materials WHERE is_active = TRUE ORDER BY name")
    return render_template(request, "form.html", {"title": f"Добавить позицию в поставку #{delivery_id}", "action": f"/deliveries/{delivery_id}/items/new", "fields": delivery_item_fields(materials), "back_url": f"/deliveries/{delivery_id}", "submit_label": "Добавить позицию"})


@router.post("/deliveries/{delivery_id}/items/new")
def delivery_item_new(
    request: Request,
    delivery_id: int,
    material_id: str = Form(...),
    quantity: str = Form(...),
    unit_price: str = Form(...),
    batch_number: str = Form(""),
    expiry_date: str = Form(...),
):
    user = authorize_action(request, "deliveries.add_item", "У вас нет прав на добавление позиций поставки.")
    if not isinstance(user, dict):
        return user
    delivery = fetch_delivery_for_user(delivery_id)
    if not delivery:
        return render_template(request, "error.html", {"title": "Поставка не найдена", "message": "Карточка поставки не найдена."}, status_code=404)
    materials = fetch_all("SELECT material_id, name FROM raw_materials WHERE is_active = TRUE ORDER BY name")
    form_data = {"material_id": material_id, "quantity": quantity, "unit_price": unit_price, "batch_number": batch_number, "expiry_date": expiry_date}

    if delivery["status_code"] not in DELIVERY_MUTABLE_STATUSES:
        return forbidden_response(request, "Нельзя добавлять позиции в поставку с этим статусом.")

    try:
        material_id_value = parse_int(material_id, "Сырьё")
        quantity_value = parse_decimal(quantity, "Количество")
        unit_price_value = parse_decimal(unit_price, "Цена за единицу")
        expiry_date_value = parse_date(expiry_date, "Срок годности")
        batch_value = clean_text(batch_number)
        if quantity_value <= 0:
            raise ValueError("Количество должно быть больше нуля.")
        if unit_price_value < 0:
            raise ValueError("Цена не может быть отрицательной.")
        if expiry_date_value <= delivery["delivery_date"]:
            raise ValueError("Срок годности должен быть позже даты поставки.")

        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
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
                if delivery["status_code"] in DELIVERY_STOCK_STATUSES:
                    sync_delivery_stock(conn, delivery_id)
        set_flash(request, "Позиция поставки успешно добавлена.")
        return redirect_to(f"/deliveries/{delivery_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"Добавить позицию в поставку #{delivery_id}", "action": f"/deliveries/{delivery_id}/items/new", "fields": delivery_item_fields(materials, form_data), "back_url": f"/deliveries/{delivery_id}", "submit_label": "Добавить позицию", "error_message": str(exc)}, status_code=400)


@router.get("/deliveries/{delivery_id}/status")
def delivery_status_page(request: Request, delivery_id: int):
    user = authorize_action(request, "deliveries.change_status", "У вас нет прав на изменение статуса поставки.")
    if not isinstance(user, dict):
        return user
    delivery = fetch_delivery_for_user(delivery_id)
    if not delivery:
        return render_template(request, "error.html", {"title": "Поставка не найдена", "message": "Карточка поставки не найдена."}, status_code=404)
    statuses = fetch_all("SELECT status_code, name FROM delivery_statuses ORDER BY name")
    return render_template(request, "form.html", {"title": f"Изменить статус поставки #{delivery_id}", "action": f"/deliveries/{delivery_id}/status", "fields": delivery_status_fields(statuses, delivery['status_code']), "back_url": f"/deliveries/{delivery_id}", "submit_label": "Обновить статус"})


@router.post("/deliveries/{delivery_id}/status")
def delivery_status_update(request: Request, delivery_id: int, status_code: str = Form(...)):
    user = authorize_action(request, "deliveries.change_status", "У вас нет прав на изменение статуса поставки.")
    if not isinstance(user, dict):
        return user
    delivery = fetch_delivery_for_user(delivery_id)
    if not delivery:
        return render_template(request, "error.html", {"title": "Поставка не найдена", "message": "Карточка поставки не найдена."}, status_code=404)
    statuses = fetch_all("SELECT status_code, name FROM delivery_statuses ORDER BY name")
    try:
        new_status = clean_text(status_code)
        if new_status not in {"planned", "received", "accepted", "rejected", "cancelled"}:
            raise ValueError("Недопустимый статус поставки.")
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
            if new_status in DELIVERY_STOCK_STATUSES:
                created_count = sync_delivery_stock(conn, delivery_id)
            else:
                created_count = 0
        if created_count:
            set_flash(request, f"Статус поставки обновлён, на склад добавлено партий: {created_count}.")
        else:
            set_flash(request, "Статус поставки успешно обновлён.")
        return redirect_to(f"/deliveries/{delivery_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"Изменить статус поставки #{delivery_id}", "action": f"/deliveries/{delivery_id}/status", "fields": delivery_status_fields(statuses, clean_text(status_code) or delivery['status_code']), "back_url": f"/deliveries/{delivery_id}", "submit_label": "Обновить статус", "error_message": str(exc)}, status_code=400)


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
            "title": "Остатки сырья",
            "subtitle": "Складские остатки по партиям. Просроченные и скоро истекающие партии подсвечены.",
            "headers": [
                ("stock_id", "ID"),
                ("material_name", "Сырьё"),
                ("batch_number", "Партия"),
                ("quantity_current", "Количество"),
                ("unit", "Ед."),
                ("expiry_date", "Срок годности"),
                ("updated_at", "Обновлено"),
            ],
            "rows": rows,
        },
    )
