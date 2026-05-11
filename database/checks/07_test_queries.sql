-- Raw material stock balances
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
ORDER BY rm.name, rms.batch_number;

-- Raw materials below minimum stock
SELECT
    rm.material_id,
    rm.name,
    rm.min_stock_qty,
    COALESCE(SUM(rms.quantity_current), 0) AS quantity_on_hand,
    rm.unit
FROM raw_materials AS rm
LEFT JOIN raw_material_stock AS rms ON rms.material_id = rm.material_id
GROUP BY rm.material_id, rm.name, rm.min_stock_qty, rm.unit
HAVING COALESCE(SUM(rms.quantity_current), 0) < rm.min_stock_qty
ORDER BY rm.name;

-- Finished goods stock balances
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
ORDER BY p.name, fgs.batch_number;

-- Customer orders for a selected customer
SELECT
    c.full_name,
    c.company_name,
    o.order_number,
    o.order_date,
    o.planned_shipment_date,
    o.status_code
FROM customer_orders AS o
JOIN customers AS c ON c.customer_id = o.customer_id
WHERE o.customer_id = 1
ORDER BY o.order_date;

-- Composition of a selected order
SELECT
    o.order_number,
    p.name AS product_name,
    oi.quantity,
    p.unit,
    oi.unit_price,
    oi.line_amount
FROM order_items AS oi
JOIN customer_orders AS o ON o.order_id = oi.order_id
JOIN products AS p ON p.product_id = oi.product_id
WHERE oi.order_id = 1
ORDER BY p.name;

-- Recipe composition for active tech cards
SELECT
    tc.card_number,
    p.name AS product_name,
    rm.name AS material_name,
    ri.stage,
    ri.quantity,
    ri.unit,
    ri.waste_percent
FROM recipe_items AS ri
JOIN tech_cards AS tc ON tc.tech_card_id = ri.tech_card_id
JOIN products AS p ON p.product_id = tc.product_id
JOIN raw_materials AS rm ON rm.material_id = ri.material_id
WHERE tc.status_code = 'active'
ORDER BY tc.card_number, ri.stage, rm.name;

-- Production for a period
SELECT
    pb.batch_number,
    p.name AS product_name,
    pb.production_date,
    pb.quantity_produced,
    pb.quantity_defective,
    pb.status_code
FROM production_batches AS pb
JOIN products AS p ON p.product_id = pb.product_id
WHERE pb.production_date::DATE BETWEEN DATE '2026-04-01' AND DATE '2026-04-10'
ORDER BY pb.production_date;

-- Sales for a period
SELECT
    o.order_number,
    p.name AS product_name,
    oi.quantity,
    oi.line_amount,
    o.order_date
FROM order_items AS oi
JOIN customer_orders AS o ON o.order_id = oi.order_id
JOIN products AS p ON p.product_id = oi.product_id
WHERE o.order_date::DATE BETWEEN DATE '2026-04-01' AND DATE '2026-04-10'
ORDER BY o.order_date, o.order_number;

-- Invoices by order
SELECT
    o.order_number,
    i.invoice_number,
    i.issue_date,
    i.due_date,
    i.amount,
    i.status_code
FROM invoices AS i
JOIN customer_orders AS o ON o.order_id = i.order_id
ORDER BY i.issue_date, i.invoice_number;

-- Shipments for a period
SELECT
    s.shipment_number,
    o.order_number,
    s.shipped_at,
    s.status_code,
    s.delivery_address
FROM shipments AS s
JOIN customer_orders AS o ON o.order_id = s.order_id
WHERE s.shipped_at::DATE BETWEEN DATE '2026-04-01' AND DATE '2026-04-10'
ORDER BY s.shipped_at;

-- Quality control for raw materials and finished products
SELECT
    qc.quality_check_id,
    qc.check_type,
    qc.document_number,
    qc.checked_at,
    qc.result_code,
    rm.name AS raw_material_name,
    p.name AS product_name,
    qc.parameter_name,
    qc.measured_value,
    qc.standard_value
FROM quality_checks AS qc
LEFT JOIN delivery_items AS di ON di.delivery_item_id = qc.delivery_item_id
LEFT JOIN raw_materials AS rm ON rm.material_id = di.material_id
LEFT JOIN production_batches AS pb ON pb.production_batch_id = qc.production_batch_id
LEFT JOIN products AS p ON p.product_id = pb.product_id
ORDER BY qc.checked_at;

-- User actions from audit log
SELECT
    al.audit_id,
    al.changed_at,
    u.username,
    al.action_type,
    al.table_name,
    al.record_id,
    al.success
FROM audit_log AS al
LEFT JOIN users AS u ON u.user_id = al.user_id
ORDER BY al.changed_at, al.audit_id;
