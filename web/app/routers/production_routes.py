from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_action, authorize_section, redirect_to, render_template, set_flash
from ..database import fetch_all, get_db, next_id
from ..permissions import has_action
from ..utils import build_options, clean_text, parse_datetime_local, parse_decimal, parse_int


router = APIRouter()


def production_fields(products, tech_cards, users, statuses, data=None):
    data = data or {}
    return [
        {"name": "product_id", "label": "Продукция", "type": "select", "required": True, "value": data.get("product_id", ""), "options": build_options(products, "product_id", "name")},
        {"name": "tech_card_id", "label": "Техкарта", "type": "select", "required": True, "value": data.get("tech_card_id", ""), "options": build_options(tech_cards, "tech_card_id", "card_label")},
        {"name": "production_date", "label": "Дата производства", "type": "datetime-local", "required": True, "value": data.get("production_date", "")},
        {"name": "shift", "label": "Смена", "type": "text", "value": data.get("shift", "")},
        {"name": "quantity_produced", "label": "Произведено", "type": "number", "required": True, "step": "0.001", "min": "0.001", "value": data.get("quantity_produced", "")},
        {"name": "quantity_defective", "label": "Брак", "type": "number", "step": "0.001", "min": "0", "value": data.get("quantity_defective", "0")},
        {"name": "responsible_user_id", "label": "Ответственный", "type": "select", "value": data.get("responsible_user_id", ""), "options": build_options(users, "user_id", "full_name", blank_label="Выберите пользователя")},
        {"name": "status_code", "label": "Статус", "type": "select", "required": True, "value": data.get("status_code", "completed"), "options": build_options(statuses, "status_code", "name")},
        {"name": "note", "label": "Примечание", "type": "textarea", "value": data.get("note", "")},
    ]


def consume_materials_for_production(conn, tech_card_id: int, produced_qty: Decimal, production_day: date):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                ri.material_id,
                rm.name AS material_name,
                ri.quantity,
                COALESCE(ri.waste_percent, 0) AS waste_percent
            FROM recipe_items AS ri
            JOIN raw_materials AS rm ON rm.material_id = ri.material_id
            WHERE ri.tech_card_id = %s
            ORDER BY ri.recipe_item_id
            """,
            (tech_card_id,),
        )
        recipe_items = cur.fetchall()
        if not recipe_items:
            raise ValueError("Для выбранной техкарты не задан состав рецепта.")

        consumptions = []
        for item in recipe_items:
            recipe_qty = Decimal(item["quantity"])
            waste_factor = Decimal("1") + (Decimal(item["waste_percent"]) / Decimal("100"))
            required_qty = produced_qty * recipe_qty * waste_factor
            cur.execute(
                """
                SELECT stock_id, quantity_current, expiry_date
                FROM raw_material_stock
                WHERE material_id = %s
                  AND quantity_current > 0
                  AND expiry_date >= %s
                ORDER BY expiry_date, stock_id
                """,
                (item["material_id"], production_day),
            )
            stock_rows = cur.fetchall()
            available_qty = sum(Decimal(row["quantity_current"]) for row in stock_rows)
            if available_qty < required_qty:
                raise ValueError(f"Недостаточно сырья «{item['material_name']}» для запуска производства.")

            remaining = required_qty
            allocations = []
            for row in stock_rows:
                if remaining <= 0:
                    break
                stock_qty = Decimal(row["quantity_current"])
                take_qty = stock_qty if stock_qty <= remaining else remaining
                allocations.append((row["stock_id"], take_qty))
                remaining -= take_qty
            consumptions.append((item["material_name"], required_qty, allocations))

        for _material_name, _required_qty, allocations in consumptions:
            for stock_id, take_qty in allocations:
                cur.execute(
                    """
                    UPDATE raw_material_stock
                    SET quantity_current = quantity_current - %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE stock_id = %s
                    """,
                    (take_qty, stock_id),
                )


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
    context = {
        "title": "Производство",
        "subtitle": "Журнал производственных партий готовой продукции.",
        "headers": [
            ("production_batch_id", "ID"),
            ("batch_number", "Номер партии"),
            ("product_name", "Продукция"),
            ("card_number", "Техкарта"),
            ("production_date", "Дата производства"),
            ("quantity_produced", "Произведено"),
            ("quantity_defective", "Брак"),
            ("status_code", "Статус"),
        ],
        "rows": rows,
    }
    if has_action(user, "production.create"):
        context["create_url"] = "/production/new"
        context["create_label"] = "Добавить партию"
    return render_template(request, "table_list.html", context)


@router.get("/production/new")
def production_new_page(request: Request):
    user = authorize_action(request, "production.create", "У вас нет прав на создание производственных партий.")
    if not isinstance(user, dict):
        return user
    products = fetch_all("SELECT product_id, name FROM products WHERE is_active = TRUE ORDER BY name")
    tech_cards = fetch_all("SELECT tech_card_id, card_number || ' / ' || version::TEXT AS card_label FROM tech_cards WHERE status_code = 'active' ORDER BY card_number")
    users = fetch_all("SELECT user_id, full_name FROM users WHERE status_code = 'active' ORDER BY full_name")
    statuses = fetch_all("SELECT status_code, name FROM production_statuses ORDER BY name")
    return render_template(request, "form.html", {"title": "Добавить производственную партию", "action": "/production/new", "fields": production_fields(products, tech_cards, users, statuses), "back_url": "/production", "submit_label": "Создать запись"})


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
    user = authorize_action(request, "production.create", "У вас нет прав на создание производственных партий.")
    if not isinstance(user, dict):
        return user
    products = fetch_all("SELECT product_id, name FROM products WHERE is_active = TRUE ORDER BY name")
    tech_cards = fetch_all("SELECT tech_card_id, card_number || ' / ' || version::TEXT AS card_label FROM tech_cards WHERE status_code = 'active' ORDER BY card_number")
    users = fetch_all("SELECT user_id, full_name FROM users WHERE status_code = 'active' ORDER BY full_name")
    statuses = fetch_all("SELECT status_code, name FROM production_statuses ORDER BY name")
    form_data = {"product_id": product_id, "tech_card_id": tech_card_id, "production_date": production_date, "shift": shift, "quantity_produced": quantity_produced, "quantity_defective": quantity_defective, "responsible_user_id": responsible_user_id, "status_code": status_code, "note": note}
    try:
        production_dt = parse_datetime_local(production_date, "Дата производства")
        produced_qty = parse_decimal(quantity_produced, "Произведено")
        defective_qty = parse_decimal(quantity_defective, "Брак")
        if produced_qty <= 0:
            raise ValueError("Количество произведённой продукции должно быть больше нуля.")
        if defective_qty < 0:
            raise ValueError("Количество брака не может быть отрицательным.")
        if defective_qty > produced_qty:
            raise ValueError("Количество брака не может превышать объём произведённой продукции.")

        product_id_value = parse_int(product_id, "Продукция")
        tech_card_id_value = parse_int(tech_card_id, "Техкарта")
        responsible_user_id_value = parse_int(responsible_user_id, "Ответственный", allow_none=True)
        net_quantity = produced_qty - defective_qty
        if net_quantity < 0:
            raise ValueError("Некорректный расчёт остатка готовой продукции.")

        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            production_batch_id = next_id(conn, "production_batches", "production_batch_id")
            batch_number = f"PB-WEB-{production_batch_id:04d}"
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT p.shelf_life_days, tc.product_id
                    FROM tech_cards AS tc
                    JOIN products AS p ON p.product_id = tc.product_id
                    WHERE tc.tech_card_id = %s
                      AND tc.product_id = %s
                    """,
                    (tech_card_id_value, product_id_value),
                )
                product_row = cur.fetchone()
                if not product_row:
                    raise ValueError("Выбранные продукция и техкарта не связаны между собой.")

                consume_materials_for_production(conn, tech_card_id_value, produced_qty, production_dt.date())

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
                        responsible_user_id_value,
                        clean_text(status_code),
                        clean_text(note),
                    ),
                )

                if net_quantity > 0:
                    finished_stock_id = next_id(conn, "finished_goods_stock", "finished_stock_id")
                    expiry_dt = production_dt.date() + timedelta(days=product_row["shelf_life_days"])
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
                            net_quantity,
                            production_dt.date(),
                            expiry_dt,
                        ),
                    )
        set_flash(request, "Производственная партия успешно создана, сырьё списано, остаток готовой продукции обновлён.")
        return redirect_to("/production")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": "Добавить производственную партию", "action": "/production/new", "fields": production_fields(products, tech_cards, users, statuses, form_data), "back_url": "/production", "submit_label": "Создать запись", "error_message": str(exc)}, status_code=400)


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
            "title": "Остатки готовой продукции",
            "subtitle": "Остатки готовой продукции по партиям с контролем сроков годности.",
            "headers": [
                ("finished_stock_id", "ID"),
                ("product_name", "Продукция"),
                ("batch_number", "Партия"),
                ("quantity_current", "Количество"),
                ("unit", "Ед."),
                ("production_date", "Дата производства"),
                ("expiry_date", "Срок годности"),
            ],
            "rows": rows,
        },
    )
