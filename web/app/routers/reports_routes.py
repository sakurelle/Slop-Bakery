from datetime import date, timedelta

from fastapi import APIRouter, Query, Request

from ..auth import authorize_section, render_template
from ..database import fetch_all


router = APIRouter()


@router.get("/reports")
def reports_page(
    request: Request,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
):
    user = authorize_section(request, "reports")
    if not isinstance(user, dict):
        return user

    default_start = (date.today() - timedelta(days=30)).isoformat()
    start_value = start_date or default_start
    end_value = end_date or date.today().isoformat()

    material_stock = fetch_all(
        """
        SELECT rm.name AS material_name, SUM(rms.quantity_current) AS quantity_on_hand, rm.unit
        FROM raw_material_stock AS rms
        JOIN raw_materials AS rm ON rm.material_id = rms.material_id
        GROUP BY rm.name, rm.unit
        ORDER BY rm.name
        """
    )
    low_stock = fetch_all(
        """
        SELECT rm.name AS material_name, rm.min_stock_qty, COALESCE(SUM(rms.quantity_current), 0) AS quantity_on_hand, rm.unit
        FROM raw_materials AS rm
        LEFT JOIN raw_material_stock AS rms ON rms.material_id = rm.material_id
        GROUP BY rm.name, rm.min_stock_qty, rm.unit
        HAVING COALESCE(SUM(rms.quantity_current), 0) < rm.min_stock_qty
        ORDER BY rm.name
        """
    )
    finished_stock = fetch_all(
        """
        SELECT p.name AS product_name, SUM(fgs.quantity_current) AS quantity_on_hand, p.unit
        FROM finished_goods_stock AS fgs
        JOIN products AS p ON p.product_id = fgs.product_id
        GROUP BY p.name, p.unit
        ORDER BY p.name
        """
    )
    orders = fetch_all(
        """
        SELECT o.order_number, COALESCE(c.company_name, c.full_name) AS customer_name, o.order_date, o.status_code
        FROM customer_orders AS o
        JOIN customers AS c ON c.customer_id = o.customer_id
        WHERE o.order_date::DATE BETWEEN %s AND %s
        ORDER BY o.order_date DESC
        """,
        (start_value, end_value),
    )
    sales = fetch_all(
        """
        SELECT p.name AS product_name, SUM(oi.quantity) AS total_quantity, SUM(oi.line_amount) AS total_amount
        FROM order_items AS oi
        JOIN customer_orders AS o ON o.order_id = oi.order_id
        JOIN products AS p ON p.product_id = oi.product_id
        WHERE o.order_date::DATE BETWEEN %s AND %s
        GROUP BY p.name
        ORDER BY total_amount DESC NULLS LAST, p.name
        """,
        (start_value, end_value),
    )
    production = fetch_all(
        """
        SELECT p.name AS product_name, pb.batch_number, pb.production_date, pb.quantity_produced, pb.quantity_defective, pb.status_code
        FROM production_batches AS pb
        JOIN products AS p ON p.product_id = pb.product_id
        WHERE pb.production_date::DATE BETWEEN %s AND %s
        ORDER BY pb.production_date DESC
        """,
        (start_value, end_value),
    )
    quality = fetch_all(
        """
        SELECT qc.check_type, qc.checked_at, qc.result_code, qc.document_number, COALESCE(rm.name, p.name) AS object_name
        FROM quality_checks AS qc
        LEFT JOIN delivery_items AS di ON di.delivery_item_id = qc.delivery_item_id
        LEFT JOIN raw_materials AS rm ON rm.material_id = di.material_id
        LEFT JOIN production_batches AS pb ON pb.production_batch_id = qc.production_batch_id
        LEFT JOIN products AS p ON p.product_id = pb.product_id
        WHERE qc.checked_at::DATE BETWEEN %s AND %s
        ORDER BY qc.checked_at DESC
        """,
        (start_value, end_value),
    )

    report_sections = [
        {"title": "Остатки сырья", "headers": [("material_name", "Сырьё"), ("quantity_on_hand", "Количество"), ("unit", "Ед.")], "rows": material_stock},
        {"title": "Сырьё ниже минимального остатка", "headers": [("material_name", "Сырьё"), ("min_stock_qty", "Минимум"), ("quantity_on_hand", "Текущий остаток"), ("unit", "Ед.")], "rows": low_stock},
        {"title": "Остатки готовой продукции", "headers": [("product_name", "Продукция"), ("quantity_on_hand", "Количество"), ("unit", "Ед.")], "rows": finished_stock},
        {"title": "Заказы за период", "headers": [("order_number", "Заказ"), ("customer_name", "Клиент"), ("order_date", "Дата заказа"), ("status_code", "Статус")], "rows": orders},
        {"title": "Продажи за период", "headers": [("product_name", "Продукция"), ("total_quantity", "Количество"), ("total_amount", "Сумма")], "rows": sales},
        {"title": "Производство за период", "headers": [("product_name", "Продукция"), ("batch_number", "Партия"), ("production_date", "Дата производства"), ("quantity_produced", "Произведено"), ("quantity_defective", "Брак"), ("status_code", "Статус")], "rows": production},
        {"title": "Контроль качества за период", "headers": [("check_type", "Тип"), ("object_name", "Объект"), ("checked_at", "Дата проверки"), ("result_code", "Результат"), ("document_number", "Документ")], "rows": quality},
    ]

    return render_template(
        request,
        "reports.html",
        {
            "title": "Отчёты",
            "start_date": start_value,
            "end_date": end_value,
            "sections": report_sections,
        },
    )
