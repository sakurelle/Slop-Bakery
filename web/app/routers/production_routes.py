from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_action, authorize_section, forbidden_response, redirect_to, render_template, set_flash
from ..database import fetch_all, fetch_one, get_db
from ..permissions import has_action
from ..utils import build_options, clean_text, parse_datetime_local, parse_decimal, parse_int


router = APIRouter()

PRODUCTION_STATUS_TRANSITIONS = {
    "planned": {"in_progress", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}

CREATABLE_PRODUCTION_STATUSES = {"planned", "in_progress", "completed"}


def production_fields(products, tech_cards, users, statuses, data=None):
    data = data or {}
    return [
        {"name": "product_id", "label": "Продукция", "type": "select", "required": True, "value": data.get("product_id", ""), "options": build_options(products, "product_id", "name")},
        {"name": "tech_card_id", "label": "Техкарта", "type": "select", "required": True, "value": data.get("tech_card_id", ""), "options": build_options(tech_cards, "tech_card_id", "card_label")},
        {"name": "production_date", "label": "Дата производства", "type": "datetime-local", "required": True, "value": data.get("production_date", "")},
        {"name": "shift", "label": "Смена", "type": "text", "value": data.get("shift", "")},
        {"name": "quantity_produced", "label": "Произведено", "type": "number", "required": True, "step": "0.001", "min": "0.001", "value": data.get("quantity_produced", "")},
        {"name": "quantity_defective", "label": "Брак", "type": "number", "step": "0.001", "min": "0", "value": data.get("quantity_defective", "0")},
        {"name": "responsible_user_id", "label": "Ответственный", "type": "select", "value": data.get("responsible_user_id", ""), "options": build_options(users, "user_id", "full_name", blank_label="Выберите технолога")},
        {"name": "status_code", "label": "Статус", "type": "select", "required": True, "value": data.get("status_code", "planned"), "options": build_options(statuses, "status_code", "name")},
        {"name": "note", "label": "Примечание", "type": "textarea", "value": data.get("note", "")},
    ]


def production_status_fields(statuses, current_status):
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


def fetch_production_batch(batch_id: int):
    return fetch_one(
        """
        SELECT
            pb.*,
            p.name AS product_name,
            tc.card_number
        FROM production_batches AS pb
        JOIN products AS p ON p.product_id = pb.product_id
        JOIN tech_cards AS tc ON tc.tech_card_id = pb.tech_card_id
        WHERE pb.production_batch_id = %s
        """,
        (batch_id,),
    )


def get_responsible_users():
    return fetch_all(
        """
        SELECT DISTINCT u.user_id, u.full_name
        FROM users AS u
        JOIN user_roles AS ur ON ur.user_id = u.user_id
        JOIN roles AS r ON r.role_id = ur.role_id
        WHERE u.status_code = 'active'
          AND r.role_code = 'technologist'
        ORDER BY u.full_name
        """
    )


def get_tech_cards():
    return fetch_all(
        """
        SELECT
            tc.tech_card_id,
            tc.card_number || ' / v' || tc.version::TEXT || ' / ' || p.name AS card_label
        FROM tech_cards AS tc
        JOIN products AS p ON p.product_id = tc.product_id
        WHERE status_code = 'active'
        ORDER BY p.name, tc.card_number, tc.version DESC
        """
    )


def get_create_statuses():
    return fetch_all(
        """
        SELECT status_code, name
        FROM production_statuses
        WHERE status_code = ANY(%s)
        ORDER BY name
        """,
        (sorted(CREATABLE_PRODUCTION_STATUSES),),
    )


def validate_responsible_user(conn, responsible_user_id: int | None):
    if responsible_user_id is None:
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
              AND r.role_code = 'technologist'
            """,
            (responsible_user_id,),
        )
        if not cur.fetchone():
            raise ValueError("Ответственным за производство может быть только активный технолог.")


def validate_tech_card(conn, tech_card_id: int, product_id: int, production_day: date):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                tc.tech_card_id,
                tc.product_id,
                tc.status_code,
                tc.effective_from,
                tc.effective_to,
                p.shelf_life_days
            FROM tech_cards AS tc
            JOIN products AS p ON p.product_id = tc.product_id
            WHERE tc.tech_card_id = %s
            """,
            (tech_card_id,),
        )
        tech_card = cur.fetchone()
        if not tech_card:
            raise ValueError("Выбранная техкарта не существует.")
        if tech_card["product_id"] != product_id:
            raise ValueError("Выбранные продукция и техкарта не связаны между собой.")
        if tech_card["status_code"] != "active":
            raise ValueError("Использовать можно только активную техкарту.")
        if tech_card["effective_from"] > production_day:
            raise ValueError("Техкарта ещё не действует на дату производства.")
        if tech_card["effective_to"] and tech_card["effective_to"] < production_day:
            raise ValueError("Срок действия техкарты истёк на дату производства.")
        return tech_card


def get_next_production_statuses(batch: dict) -> list[str]:
    return sorted(PRODUCTION_STATUS_TRANSITIONS.get(batch["status_code"], set()))


def fetch_production_status_options(batch: dict):
    next_statuses = get_next_production_statuses(batch)
    if not next_statuses:
        return []
    return fetch_all(
        """
        SELECT status_code, name
        FROM production_statuses
        WHERE status_code = ANY(%s)
        ORDER BY name
        """,
        (next_statuses,),
    )


def validate_production_status_change(batch: dict, new_status: str):
    if new_status not in PRODUCTION_STATUS_TRANSITIONS.get(batch["status_code"], set()):
        raise ValueError("Недопустимый переход статуса производственной партии.")


def consume_materials_for_production(conn, tech_card_id: int, produced_qty: Decimal, production_day: date, apply_changes: bool = True):
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
            raise ValueError("Для выбранной техкарты не задан состав рецептуры.")

        consumptions = []
        for item in recipe_items:
            recipe_qty = Decimal(item["quantity"])
            waste_factor = Decimal("1") + (Decimal(item["waste_percent"]) / Decimal("100"))
            required_qty = produced_qty * recipe_qty * waste_factor

            cur.execute(
                """
                SELECT 1
                FROM raw_material_stock AS rms
                WHERE rms.material_id = %s
                  AND rms.quantity_current > 0
                  AND rms.expiry_date >= %s
                LIMIT 1
                """,
                (item["material_id"], production_day),
            )
            has_any_stock = cur.fetchone()

            cur.execute(
                """
                SELECT
                    rms.stock_id,
                    rms.quantity_current,
                    rms.expiry_date
                FROM raw_material_stock AS rms
                WHERE rms.material_id = %s
                  AND rms.quantity_current > 0
                  AND rms.expiry_date >= %s
                  AND EXISTS (
                      SELECT 1
                      FROM quality_checks AS qc_passed
                      WHERE qc_passed.delivery_item_id = rms.delivery_item_id
                        AND qc_passed.check_type = 'raw_material'
                        AND qc_passed.result_code = 'passed'
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM quality_checks AS qc_failed
                      WHERE qc_failed.delivery_item_id = rms.delivery_item_id
                        AND qc_failed.check_type = 'raw_material'
                        AND qc_failed.result_code = 'failed'
                  )
                ORDER BY rms.expiry_date, rms.stock_id
                """,
                (item["material_id"], production_day),
            )
            stock_rows = cur.fetchall()
            if has_any_stock and not stock_rows:
                raise ValueError(f"Сырьё «{item['material_name']}» нельзя использовать: нет успешной проверки качества.")
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
            consumptions.append(allocations)

        if not apply_changes:
            return

        for allocations in consumptions:
            for stock_id, take_qty in allocations:
                cur.execute(
                    """
                    UPDATE raw_material_stock
                    SET quantity_current = quantity_current - %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE stock_id = %s
                      AND quantity_current >= %s
                    """,
                    (take_qty, stock_id, take_qty),
                )
                if cur.rowcount != 1:
                    raise ValueError("Не удалось корректно списать сырьё со склада.")


def finalize_production_batch(conn, batch: dict, tech_card: dict):
    produced_qty = Decimal(batch["quantity_produced"])
    defective_qty = Decimal(batch["quantity_defective"])
    net_quantity = produced_qty - defective_qty
    production_day = batch["production_date"].date()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM finished_goods_stock
            WHERE production_batch_id = %s
            LIMIT 1
            """,
            (batch["production_batch_id"],),
        )
        if cur.fetchone():
            raise ValueError("Эта производственная партия уже завершена и размещена на складе.")

    consume_materials_for_production(conn, batch["tech_card_id"], produced_qty, production_day)

    if net_quantity > 0:
        expiry_dt = production_day + timedelta(days=tech_card["shelf_life_days"])
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO finished_goods_stock (
                    product_id, production_batch_id, batch_number,
                    quantity_current, production_date, expiry_date
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    batch["product_id"],
                    batch["production_batch_id"],
                    batch["batch_number"],
                    net_quantity,
                    production_day,
                    expiry_dt,
                ),
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
    for row in rows:
        if has_action(user, "production.change_status"):
            row["_detail_url"] = f"/production/{row['production_batch_id']}/status"
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
    return render_template(
        request,
        "form.html",
        {
            "title": "Добавить производственную партию",
            "action": "/production/new",
            "fields": production_fields(products, get_tech_cards(), get_responsible_users(), get_create_statuses()),
            "back_url": "/production",
            "submit_label": "Создать запись",
        },
    )


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
    tech_cards = get_tech_cards()
    responsible_users = get_responsible_users()
    statuses = get_create_statuses()
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
        status_value = clean_text(status_code)
        if status_value not in CREATABLE_PRODUCTION_STATUSES:
            raise ValueError("Недопустимый стартовый статус производственной партии.")

        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            validate_responsible_user(conn, responsible_user_id_value)
            tech_card = validate_tech_card(conn, tech_card_id_value, product_id_value, production_dt.date())
            if status_value in {"in_progress", "completed"}:
                consume_materials_for_production(conn, tech_card_id_value, produced_qty, production_dt.date(), apply_changes=False)

            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH new_batch AS (
                        SELECT nextval(pg_get_serial_sequence('production_batches', 'production_batch_id')) AS production_batch_id
                    )
                    INSERT INTO production_batches (
                        production_batch_id, batch_number, product_id, tech_card_id, production_date,
                        shift, quantity_produced, quantity_defective, responsible_user_id, status_code, note
                    )
                    SELECT
                        new_batch.production_batch_id,
                        'PB-WEB-' || LPAD(new_batch.production_batch_id::TEXT, 4, '0'),
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    FROM new_batch
                    RETURNING production_batch_id, batch_number
                    """,
                    (
                        product_id_value,
                        tech_card_id_value,
                        production_dt,
                        clean_text(shift),
                        produced_qty,
                        defective_qty,
                        responsible_user_id_value,
                        status_value,
                        clean_text(note),
                    ),
                )
                created_batch = cur.fetchone()
                production_batch_id = created_batch["production_batch_id"]
                batch_number = created_batch["batch_number"]

            if status_value == "completed":
                finalize_production_batch(
                    conn,
                    {
                        "production_batch_id": production_batch_id,
                        "batch_number": batch_number,
                        "product_id": product_id_value,
                        "tech_card_id": tech_card_id_value,
                        "production_date": production_dt,
                        "quantity_produced": produced_qty,
                        "quantity_defective": defective_qty,
                    },
                    tech_card,
                )

        if status_value == "completed":
            set_flash(request, "Производственная партия завершена: сырьё списано, готовая продукция добавлена на склад.")
        else:
            set_flash(request, "Производственная партия создана без движения складских остатков до завершения.")
        return redirect_to("/production")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "Не удалось сохранить производственную партию."

    return render_template(
        request,
        "form.html",
        {
            "title": "Добавить производственную партию",
            "action": "/production/new",
            "fields": production_fields(products, tech_cards, responsible_users, statuses, form_data),
            "back_url": "/production",
            "submit_label": "Создать запись",
            "error_message": error_message,
        },
        status_code=400,
    )


@router.get("/production/{production_batch_id}/status")
def production_status_page(request: Request, production_batch_id: int):
    user = authorize_action(request, "production.change_status", "У вас нет прав на изменение статуса производства.")
    if not isinstance(user, dict):
        return user
    batch = fetch_production_batch(production_batch_id)
    if not batch:
        return render_template(request, "error.html", {"title": "Партия не найдена", "message": "Карточка производственной партии не найдена."}, status_code=404)
    statuses = fetch_production_status_options(batch)
    if not statuses:
        return forbidden_response(request, "Для текущего статуса производственной партии нет допустимых переходов.")
    return render_template(
        request,
        "form.html",
        {
            "title": f"Изменить статус партии #{production_batch_id}",
            "action": f"/production/{production_batch_id}/status",
            "fields": production_status_fields(statuses, statuses[0]["status_code"]),
            "back_url": "/production",
            "submit_label": "Обновить статус",
        },
    )


@router.post("/production/{production_batch_id}/status")
def production_status_update(request: Request, production_batch_id: int, status_code: str = Form(...)):
    user = authorize_action(request, "production.change_status", "У вас нет прав на изменение статуса производства.")
    if not isinstance(user, dict):
        return user
    batch = fetch_production_batch(production_batch_id)
    if not batch:
        return render_template(request, "error.html", {"title": "Партия не найдена", "message": "Карточка производственной партии не найдена."}, status_code=404)
    statuses = fetch_production_status_options(batch)
    try:
        new_status = clean_text(status_code)
        if not new_status:
            raise ValueError("Не выбран новый статус производственной партии.")
        validate_production_status_change(batch, new_status)

        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            validate_responsible_user(conn, batch["responsible_user_id"])
            tech_card = validate_tech_card(conn, batch["tech_card_id"], batch["product_id"], batch["production_date"].date())

            if new_status == "in_progress":
                consume_materials_for_production(conn, batch["tech_card_id"], Decimal(batch["quantity_produced"]), batch["production_date"].date(), apply_changes=False)
            if new_status == "completed":
                finalize_production_batch(conn, batch, tech_card)

            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE production_batches SET status_code = %s WHERE production_batch_id = %s",
                    (new_status, production_batch_id),
                )

        if new_status == "completed":
            set_flash(request, "Партия завершена: сырьё списано, готовая продукция добавлена на склад.")
        else:
            set_flash(request, "Статус производственной партии обновлён.")
        return redirect_to("/production")
    except ValueError as exc:
        error_message = str(exc)
    except PsycopgError:
        error_message = "Не удалось изменить статус производственной партии."

    return render_template(
        request,
        "form.html",
        {
            "title": f"Изменить статус партии #{production_batch_id}",
            "action": f"/production/{production_batch_id}/status",
            "fields": production_status_fields(statuses, clean_text(status_code) or batch["status_code"]),
            "back_url": "/production",
            "submit_label": "Обновить статус",
            "error_message": error_message,
        },
        status_code=400,
    )


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
