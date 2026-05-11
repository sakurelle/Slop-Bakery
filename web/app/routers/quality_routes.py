from fastapi import APIRouter, Form, Query, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_section, redirect_to, render_template, set_flash
from ..database import fetch_all, get_db, next_id
from ..utils import build_options, clean_text, parse_datetime_local, parse_int


router = APIRouter()


def quality_fields(delivery_items, production_batches, inspectors, results, data=None):
    data = data or {}
    return [
        {
            "name": "check_type",
            "label": "Тип проверки",
            "type": "select",
            "required": True,
            "value": data.get("check_type", "raw_material"),
            "options": [
                {"value": "raw_material", "label": "Сырьё"},
                {"value": "finished_product", "label": "Готовая продукция"},
            ],
        },
        {
            "name": "delivery_item_id",
            "label": "Позиция поставки",
            "type": "select",
            "value": data.get("delivery_item_id", ""),
            "options": build_options(delivery_items, "delivery_item_id", "display_name", blank_label="Не выбрано"),
        },
        {
            "name": "production_batch_id",
            "label": "Производственная партия",
            "type": "select",
            "value": data.get("production_batch_id", ""),
            "options": build_options(production_batches, "production_batch_id", "display_name", blank_label="Не выбрано"),
        },
        {"name": "checked_at", "label": "Дата проверки", "type": "datetime-local", "required": True, "value": data.get("checked_at", "")},
        {
            "name": "inspector_user_id",
            "label": "Инспектор",
            "type": "select",
            "value": data.get("inspector_user_id", ""),
            "options": build_options(inspectors, "user_id", "full_name", blank_label="Выберите инспектора"),
        },
        {
            "name": "result_code",
            "label": "Результат",
            "type": "select",
            "required": True,
            "value": data.get("result_code", "passed"),
            "options": build_options(results, "status_code", "name"),
        },
        {"name": "parameter_name", "label": "Параметр", "type": "text", "value": data.get("parameter_name", "")},
        {"name": "measured_value", "label": "Измеренное значение", "type": "text", "value": data.get("measured_value", "")},
        {"name": "standard_value", "label": "Норма", "type": "text", "value": data.get("standard_value", "")},
        {"name": "document_number", "label": "Номер документа", "type": "text", "value": data.get("document_number", "")},
        {"name": "note", "label": "Примечание", "type": "textarea", "value": data.get("note", "")},
    ]


@router.get("/quality")
def quality_list(
    request: Request,
    check_type: str | None = Query(default=None),
    result_code: str | None = Query(default=None),
):
    user = authorize_section(request, "quality")
    if not isinstance(user, dict):
        return user
    filters = []
    params = []
    if check_type:
        filters.append("qc.check_type = %s")
        params.append(check_type)
    if result_code:
        filters.append("qc.result_code = %s")
        params.append(result_code)
    query = """
        SELECT
            qc.quality_check_id,
            qc.check_type,
            qc.checked_at,
            qc.result_code,
            qc.document_number,
            COALESCE(rm.name, p.name) AS object_name
        FROM quality_checks AS qc
        LEFT JOIN delivery_items AS di ON di.delivery_item_id = qc.delivery_item_id
        LEFT JOIN raw_materials AS rm ON rm.material_id = di.material_id
        LEFT JOIN production_batches AS pb ON pb.production_batch_id = qc.production_batch_id
        LEFT JOIN products AS p ON p.product_id = pb.product_id
    """
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY qc.checked_at DESC, qc.quality_check_id DESC"
    rows = fetch_all(query, tuple(params))
    return render_template(
        request,
        "table_list.html",
        {
            "title": "Контроль качества",
            "subtitle": "Журнал контроля качества сырья и готовой продукции.",
            "headers": [
                ("quality_check_id", "ID"),
                ("check_type", "Тип"),
                ("object_name", "Объект"),
                ("checked_at", "Дата проверки"),
                ("result_code", "Результат"),
                ("document_number", "Документ"),
            ],
            "rows": rows,
            "create_url": "/quality/new",
            "create_label": "Добавить проверку",
            "filters": {
                "action": "/quality",
                "fields": [
                    {
                        "name": "check_type",
                        "label": "Тип проверки",
                        "type": "select",
                        "value": check_type or "",
                        "options": [
                            {"value": "", "label": "Все типы"},
                            {"value": "raw_material", "label": "Сырьё"},
                            {"value": "finished_product", "label": "Готовая продукция"},
                        ],
                    },
                    {
                        "name": "result_code",
                        "label": "Результат",
                        "type": "select",
                        "value": result_code or "",
                        "options": [
                            {"value": "", "label": "Все результаты"},
                            {"value": "passed", "label": "Соответствует"},
                            {"value": "failed", "label": "Не соответствует"},
                            {"value": "conditional", "label": "Условно"},
                        ],
                    },
                ],
                "show_filters": True,
            },
        },
    )


@router.get("/quality/new")
def quality_new_page(request: Request):
    user = authorize_section(request, "quality")
    if not isinstance(user, dict):
        return user
    delivery_items = fetch_all(
        """
        SELECT di.delivery_item_id, rm.name || ' / ' || COALESCE(di.batch_number, 'без партии') AS display_name
        FROM delivery_items AS di
        JOIN raw_materials AS rm ON rm.material_id = di.material_id
        ORDER BY di.delivery_item_id DESC
        """
    )
    production_batches = fetch_all(
        """
        SELECT pb.production_batch_id, pb.batch_number || ' / ' || p.name AS display_name
        FROM production_batches AS pb
        JOIN products AS p ON p.product_id = pb.product_id
        ORDER BY pb.production_batch_id DESC
        """
    )
    inspectors = fetch_all("SELECT user_id, full_name FROM users WHERE status_code = 'active' ORDER BY full_name")
    results = fetch_all("SELECT status_code, name FROM quality_statuses ORDER BY name")
    return render_template(request, "form.html", {"title": "Добавить проверку качества", "action": "/quality/new", "fields": quality_fields(delivery_items, production_batches, inspectors, results), "back_url": "/quality", "submit_label": "Создать запись"})


@router.post("/quality/new")
def quality_new(
    request: Request,
    check_type: str = Form(...),
    delivery_item_id: str = Form(""),
    production_batch_id: str = Form(""),
    checked_at: str = Form(...),
    inspector_user_id: str = Form(""),
    result_code: str = Form(...),
    parameter_name: str = Form(""),
    measured_value: str = Form(""),
    standard_value: str = Form(""),
    document_number: str = Form(""),
    note: str = Form(""),
):
    user = authorize_section(request, "quality")
    if not isinstance(user, dict):
        return user
    delivery_items = fetch_all(
        """
        SELECT di.delivery_item_id, rm.name || ' / ' || COALESCE(di.batch_number, 'без партии') AS display_name
        FROM delivery_items AS di
        JOIN raw_materials AS rm ON rm.material_id = di.material_id
        ORDER BY di.delivery_item_id DESC
        """
    )
    production_batches = fetch_all(
        """
        SELECT pb.production_batch_id, pb.batch_number || ' / ' || p.name AS display_name
        FROM production_batches AS pb
        JOIN products AS p ON p.product_id = pb.product_id
        ORDER BY pb.production_batch_id DESC
        """
    )
    inspectors = fetch_all("SELECT user_id, full_name FROM users WHERE status_code = 'active' ORDER BY full_name")
    results = fetch_all("SELECT status_code, name FROM quality_statuses ORDER BY name")
    form_data = {"check_type": check_type, "delivery_item_id": delivery_item_id, "production_batch_id": production_batch_id, "checked_at": checked_at, "inspector_user_id": inspector_user_id, "result_code": result_code, "parameter_name": parameter_name, "measured_value": measured_value, "standard_value": standard_value, "document_number": document_number, "note": note}
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            quality_check_id = next_id(conn, "quality_checks", "quality_check_id")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO quality_checks (
                        quality_check_id, check_type, delivery_item_id, production_batch_id, checked_at,
                        inspector_user_id, result_code, parameter_name, measured_value,
                        standard_value, document_number, note
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        quality_check_id,
                        clean_text(check_type),
                        parse_int(delivery_item_id, "Позиция поставки", allow_none=True),
                        parse_int(production_batch_id, "Производственная партия", allow_none=True),
                        parse_datetime_local(checked_at, "Дата проверки"),
                        parse_int(inspector_user_id, "Инспектор", allow_none=True),
                        clean_text(result_code),
                        clean_text(parameter_name),
                        clean_text(measured_value),
                        clean_text(standard_value),
                        clean_text(document_number),
                        clean_text(note),
                    ),
                )
        set_flash(request, "Проверка качества успешно добавлена.")
        return redirect_to("/quality")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": "Добавить проверку качества", "action": "/quality/new", "fields": quality_fields(delivery_items, production_batches, inspectors, results, form_data), "back_url": "/quality", "submit_label": "Создать запись", "error_message": str(exc)}, status_code=400)
