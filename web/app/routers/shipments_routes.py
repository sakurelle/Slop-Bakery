from fastapi import APIRouter, Form, Request
from psycopg import Error as PsycopgError

from ..auth import authorize_section, redirect_to, render_template, set_flash
from ..database import fetch_all, fetch_one, get_db, next_id
from ..utils import build_options, clean_text, parse_datetime_local, parse_decimal


router = APIRouter()


def shipment_fields(orders, statuses, data=None):
    data = data or {}
    return [
        {"name": "order_id", "label": "Order", "type": "select", "required": True, "value": data.get("order_id", ""), "options": build_options(orders, "order_id", "display_name")},
        {"name": "shipped_at", "label": "Shipped At", "type": "datetime-local", "value": data.get("shipped_at", "")},
        {"name": "status_code", "label": "Status", "type": "select", "required": True, "value": data.get("status_code", "planned"), "options": build_options(statuses, "status_code", "name")},
        {"name": "delivery_address", "label": "Delivery Address", "type": "textarea", "required": True, "value": data.get("delivery_address", "")},
        {"name": "waybill_number", "label": "Waybill Number", "type": "text", "value": data.get("waybill_number", "")},
        {"name": "note", "label": "Note", "type": "textarea", "value": data.get("note", "")},
    ]


def shipment_item_fields(order_items, products, finished_stock, data=None):
    data = data or {}
    return [
        {"name": "order_item_id", "label": "Order Item", "type": "select", "required": True, "value": data.get("order_item_id", ""), "options": build_options(order_items, "order_item_id", "display_name")},
        {"name": "product_id", "label": "Product", "type": "select", "required": True, "value": data.get("product_id", ""), "options": build_options(products, "product_id", "name")},
        {"name": "finished_stock_id", "label": "Finished Stock", "type": "select", "value": data.get("finished_stock_id", ""), "options": build_options(finished_stock, "finished_stock_id", "display_name", blank_label="Not linked")},
        {"name": "quantity", "label": "Quantity", "type": "number", "required": True, "step": "0.001", "min": "0.001", "value": data.get("quantity", "")},
    ]


@router.get("/shipments")
def shipments_list(request: Request):
    user = authorize_section(request, "shipments")
    if not isinstance(user, dict):
        return user
    query = """
        SELECT
            s.shipment_id,
            s.shipment_number,
            o.order_number,
            s.shipped_at,
            s.status_code,
            s.waybill_number
        FROM shipments AS s
        JOIN customer_orders AS o ON o.order_id = s.order_id
    """
    params = ()
    if "client" in user.get("roles", []):
        query += " WHERE o.customer_id = %s "
        params = (user["customer_id"],)
    query += " ORDER BY s.shipped_at DESC NULLS LAST, s.shipment_id DESC"
    rows = fetch_all(query, params)
    for row in rows:
        row["_detail_url"] = f"/shipments/{row['shipment_id']}"
    context = {
        "title": "Shipments",
        "subtitle": "Shipment documents and dispatch status.",
        "headers": [
            ("shipment_id", "ID"),
            ("shipment_number", "Shipment Number"),
            ("order_number", "Order"),
            ("shipped_at", "Shipped At"),
            ("status_code", "Status"),
            ("waybill_number", "Waybill"),
        ],
        "rows": rows,
    }
    if "client" not in user.get("roles", []):
        context["create_url"] = "/shipments/new"
        context["create_label"] = "Create Shipment"
    return render_template(request, "table_list.html", context)


@router.get("/shipments/new")
def shipment_new_page(request: Request):
    user = authorize_section(request, "shipments")
    if not isinstance(user, dict):
        return user
    if "client" in user.get("roles", []):
        return render_template(request, "error.html", {"title": "Access denied", "message": "Clients can only view shipments."}, status_code=403)
    orders = fetch_all("SELECT order_id, order_number || ' / ' || status_code AS display_name FROM customer_orders ORDER BY order_id DESC")
    statuses = fetch_all("SELECT status_code, name FROM shipment_statuses ORDER BY name")
    return render_template(request, "form.html", {"title": "Create Shipment", "action": "/shipments/new", "fields": shipment_fields(orders, statuses), "back_url": "/shipments", "submit_label": "Create Shipment"})


@router.post("/shipments/new")
def shipment_new(
    request: Request,
    order_id: str = Form(...),
    shipped_at: str = Form(""),
    status_code: str = Form(...),
    delivery_address: str = Form(...),
    waybill_number: str = Form(""),
    note: str = Form(""),
):
    user = authorize_section(request, "shipments")
    if not isinstance(user, dict):
        return user
    if "client" in user.get("roles", []):
        return render_template(request, "error.html", {"title": "Access denied", "message": "Clients can only view shipments."}, status_code=403)
    orders = fetch_all("SELECT order_id, order_number || ' / ' || status_code AS display_name FROM customer_orders ORDER BY order_id DESC")
    statuses = fetch_all("SELECT status_code, name FROM shipment_statuses ORDER BY name")
    form_data = {"order_id": order_id, "shipped_at": shipped_at, "status_code": status_code, "delivery_address": delivery_address, "waybill_number": waybill_number, "note": note}
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            shipment_id = next_id(conn, "shipments", "shipment_id")
            shipment_number = f"SHP-WEB-{shipment_id:04d}"
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO shipments (
                        shipment_id, shipment_number, order_id, shipped_at, status_code,
                        delivery_address, waybill_number, created_by_user_id, note
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        shipment_id,
                        shipment_number,
                        int(order_id),
                        parse_datetime_local(shipped_at, "Shipped At", allow_none=True),
                        clean_text(status_code),
                        clean_text(delivery_address),
                        clean_text(waybill_number),
                        user["user_id"],
                        clean_text(note),
                    ),
                )
        set_flash(request, "Shipment created. Add shipment items on the detail page.")
        return redirect_to(f"/shipments/{shipment_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": "Create Shipment", "action": "/shipments/new", "fields": shipment_fields(orders, statuses, form_data), "back_url": "/shipments", "submit_label": "Create Shipment", "error_message": str(exc)}, status_code=400)


@router.get("/shipments/{shipment_id}")
def shipment_detail(request: Request, shipment_id: int):
    user = authorize_section(request, "shipments")
    if not isinstance(user, dict):
        return user
    query = """
        SELECT
            s.*,
            o.order_number
        FROM shipments AS s
        JOIN customer_orders AS o ON o.order_id = s.order_id
        WHERE s.shipment_id = %s
    """
    params = [shipment_id]
    if "client" in user.get("roles", []):
        query += " AND o.customer_id = %s"
        params.append(user["customer_id"])
    shipment = fetch_one(query, tuple(params))
    if not shipment:
        return render_template(request, "error.html", {"title": "Shipment not found", "message": "Shipment record not found or unavailable."}, status_code=404)
    items = fetch_all(
        """
        SELECT si.shipment_item_id, p.name AS product_name, si.quantity, si.finished_stock_id
        FROM shipment_items AS si
        JOIN products AS p ON p.product_id = si.product_id
        WHERE si.shipment_id = %s
        ORDER BY si.shipment_item_id
        """,
        (shipment_id,),
    )
    extra_actions = []
    if "client" not in user.get("roles", []):
        extra_actions = [{"label": "Add Shipment Item", "url": f"/shipments/{shipment_id}/items/new"}, {"label": "Change Status", "url": f"/shipments/{shipment_id}/status"}]
    return render_template(
        request,
        "detail.html",
        {
            "title": shipment["shipment_number"],
            "back_url": "/shipments",
            "extra_actions": extra_actions,
            "details": [
                ("ID", shipment["shipment_id"]),
                ("Order", shipment["order_number"]),
                ("Shipped At", shipment["shipped_at"]),
                ("Status", shipment["status_code"]),
                ("Delivery Address", shipment["delivery_address"]),
                ("Waybill Number", shipment["waybill_number"]),
                ("Note", shipment["note"]),
            ],
            "sections": [
                {
                    "title": "Shipment Items",
                    "headers": [("shipment_item_id", "ID"), ("product_name", "Product"), ("quantity", "Quantity"), ("finished_stock_id", "Finished Stock ID")],
                    "rows": items,
                    "empty_message": "No shipment items added yet.",
                }
            ],
        },
    )


@router.get("/shipments/{shipment_id}/items/new")
def shipment_item_new_page(request: Request, shipment_id: int):
    user = authorize_section(request, "shipments")
    if not isinstance(user, dict):
        return user
    shipment = fetch_one("SELECT order_id FROM shipments WHERE shipment_id = %s", (shipment_id,))
    if not shipment:
        return render_template(request, "error.html", {"title": "Shipment not found", "message": "Shipment record not found."}, status_code=404)
    order_items = fetch_all(
        """
        SELECT oi.order_item_id, p.name || ' / qty ' || oi.quantity::TEXT AS display_name
        FROM order_items AS oi
        JOIN products AS p ON p.product_id = oi.product_id
        WHERE oi.order_id = %s
        ORDER BY oi.order_item_id
        """,
        (shipment["order_id"],),
    )
    products = fetch_all(
        """
        SELECT DISTINCT p.product_id, p.name
        FROM order_items AS oi
        JOIN products AS p ON p.product_id = oi.product_id
        WHERE oi.order_id = %s
        ORDER BY p.name
        """,
        (shipment["order_id"],),
    )
    finished_stock = fetch_all(
        """
        SELECT finished_stock_id, batch_number || ' / qty ' || quantity_current::TEXT AS display_name
        FROM finished_goods_stock
        ORDER BY finished_stock_id DESC
        """,
    )
    return render_template(request, "form.html", {"title": f"Add Shipment Item to #{shipment_id}", "action": f"/shipments/{shipment_id}/items/new", "fields": shipment_item_fields(order_items, products, finished_stock), "back_url": f"/shipments/{shipment_id}", "submit_label": "Add Shipment Item"})


@router.post("/shipments/{shipment_id}/items/new")
def shipment_item_new(
    request: Request,
    shipment_id: int,
    order_item_id: str = Form(...),
    product_id: str = Form(...),
    finished_stock_id: str = Form(""),
    quantity: str = Form(...),
):
    user = authorize_section(request, "shipments")
    if not isinstance(user, dict):
        return user
    shipment = fetch_one("SELECT order_id FROM shipments WHERE shipment_id = %s", (shipment_id,))
    if not shipment:
        return render_template(request, "error.html", {"title": "Shipment not found", "message": "Shipment record not found."}, status_code=404)
    order_items = fetch_all(
        """
        SELECT oi.order_item_id, p.name || ' / qty ' || oi.quantity::TEXT AS display_name
        FROM order_items AS oi
        JOIN products AS p ON p.product_id = oi.product_id
        WHERE oi.order_id = %s
        ORDER BY oi.order_item_id
        """,
        (shipment["order_id"],),
    )
    products = fetch_all(
        """
        SELECT DISTINCT p.product_id, p.name
        FROM order_items AS oi
        JOIN products AS p ON p.product_id = oi.product_id
        WHERE oi.order_id = %s
        ORDER BY p.name
        """,
        (shipment["order_id"],),
    )
    finished_stock = fetch_all("SELECT finished_stock_id, batch_number || ' / qty ' || quantity_current::TEXT AS display_name FROM finished_goods_stock ORDER BY finished_stock_id DESC")
    form_data = {"order_item_id": order_item_id, "product_id": product_id, "finished_stock_id": finished_stock_id, "quantity": quantity}
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            shipment_item_id = next_id(conn, "shipment_items", "shipment_item_id")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO shipment_items (
                        shipment_item_id, shipment_id, order_item_id, product_id, finished_stock_id, quantity
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        shipment_item_id,
                        shipment_id,
                        int(order_item_id),
                        int(product_id),
                        int(finished_stock_id) if finished_stock_id else None,
                        parse_decimal(quantity, "Quantity"),
                    ),
                )
        set_flash(request, "Shipment item added successfully.")
        return redirect_to(f"/shipments/{shipment_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"Add Shipment Item to #{shipment_id}", "action": f"/shipments/{shipment_id}/items/new", "fields": shipment_item_fields(order_items, products, finished_stock, form_data), "back_url": f"/shipments/{shipment_id}", "submit_label": "Add Shipment Item", "error_message": str(exc)}, status_code=400)


@router.get("/shipments/{shipment_id}/status")
def shipment_status_page(request: Request, shipment_id: int):
    user = authorize_section(request, "shipments")
    if not isinstance(user, dict):
        return user
    if "client" in user.get("roles", []):
        return render_template(request, "error.html", {"title": "Access denied", "message": "Clients can only view shipments."}, status_code=403)
    shipment = fetch_one("SELECT shipment_id, status_code FROM shipments WHERE shipment_id = %s", (shipment_id,))
    if not shipment:
        return render_template(request, "error.html", {"title": "Shipment not found", "message": "Shipment record not found."}, status_code=404)
    statuses = fetch_all("SELECT status_code, name FROM shipment_statuses ORDER BY name")
    return render_template(request, "form.html", {"title": f"Change Status for Shipment #{shipment_id}", "action": f"/shipments/{shipment_id}/status", "fields": [{"name": "status_code", "label": "Status", "type": "select", "required": True, "value": shipment['status_code'], "options": build_options(statuses, 'status_code', 'name')}], "back_url": f"/shipments/{shipment_id}", "submit_label": "Update Status"})


@router.post("/shipments/{shipment_id}/status")
def shipment_status_update(request: Request, shipment_id: int, status_code: str = Form(...)):
    user = authorize_section(request, "shipments")
    if not isinstance(user, dict):
        return user
    if "client" in user.get("roles", []):
        return render_template(request, "error.html", {"title": "Access denied", "message": "Clients can only view shipments."}, status_code=403)
    statuses = fetch_all("SELECT status_code, name FROM shipment_statuses ORDER BY name")
    try:
        with get_db(user_id=user["user_id"], user_ip=request.client.host if request.client else None) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE shipments SET status_code = %s WHERE shipment_id = %s", (clean_text(status_code), shipment_id))
        set_flash(request, "Shipment status updated successfully.")
        return redirect_to(f"/shipments/{shipment_id}")
    except (PsycopgError, ValueError) as exc:
        return render_template(request, "form.html", {"title": f"Change Status for Shipment #{shipment_id}", "action": f"/shipments/{shipment_id}/status", "fields": [{"name": "status_code", "label": "Status", "type": "select", "required": True, "value": status_code, "options": build_options(statuses, 'status_code', 'name')}], "back_url": f"/shipments/{shipment_id}", "submit_label": "Update Status", "error_message": str(exc)}, status_code=400)
