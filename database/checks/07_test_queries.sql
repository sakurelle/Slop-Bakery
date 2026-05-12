-- =========================================================
-- 1. Запросы на ввод данных, 3 запроса
-- =========================================================

BEGIN;

INSERT INTO order_statuses (status_code, name, description)
VALUES ('test_check_status', 'Test Check Status', 'Temporary status for repeatable SQL checks.')
ON CONFLICT (status_code) DO NOTHING;

INSERT INTO products (name, category, unit, price, shelf_life_days, is_active)
SELECT 'Demo SQL Check Product', 'Demo', 'piece', 1.00, 1, FALSE
WHERE NOT EXISTS (
    SELECT 1
    FROM products
    WHERE name = 'Demo SQL Check Product'
);

INSERT INTO customers (
    customer_type,
    full_name,
    phone,
    delivery_address,
    is_active
)
VALUES (
    'individual',
    'Temporary SQL Check Customer',
    '+7-000-000-00-00',
    'Temporary SQL check address',
    FALSE
);
ROLLBACK;

-- =========================================================
-- 2. Запросы на выборку данных в указанном порядке, 3 запроса
-- =========================================================

SELECT product_id, name, category, price
FROM products
ORDER BY category ASC, price DESC, name ASC;

SELECT order_id, order_number, order_date, planned_shipment_date, status_code
FROM customer_orders
ORDER BY order_date DESC, order_number ASC;

SELECT shipment_id, shipment_number, shipped_at, status_code
FROM shipments
ORDER BY shipped_at NULLS LAST, shipment_number;

-- =========================================================
-- 3. Запросы с исключением дубликатов, 2 запроса
-- =========================================================

SELECT DISTINCT category
FROM products
WHERE category IS NOT NULL
ORDER BY category;

SELECT DISTINCT status_code
FROM customer_orders
ORDER BY status_code;

-- =========================================================
-- 4. Запросы с константами и выражениями, 4 запроса
-- =========================================================

SELECT
    'Позиция заказа' AS object_type,
    oi.order_item_id,
    oi.quantity,
    oi.unit_price,
    oi.quantity * oi.unit_price AS calculated_line_amount
FROM order_items AS oi
ORDER BY oi.order_item_id;

SELECT
    p.product_id,
    p.name,
    p.price,
    ROUND(p.price * 1.10, 2) AS price_with_markup
FROM products AS p
ORDER BY p.product_id;

SELECT
    rm.material_id,
    rm.name,
    rm.min_stock_qty,
    COALESCE(SUM(rms.quantity_current), 0) AS quantity_on_hand,
    rm.min_stock_qty - COALESCE(SUM(rms.quantity_current), 0) AS shortage_qty
FROM raw_materials AS rm
LEFT JOIN raw_material_stock AS rms ON rms.material_id = rm.material_id
GROUP BY rm.material_id, rm.name, rm.min_stock_qty
ORDER BY rm.name;

SELECT
    invoice_id,
    invoice_number,
    amount,
    amount * 0.20 AS vat_estimate,
    'RUB' AS currency_code
FROM invoices
ORDER BY invoice_id;

-- =========================================================
-- 5. Запросы с группировкой и упорядочиванием, 2 запроса
-- =========================================================

SELECT
    o.customer_id,
    COUNT(*) AS orders_count
FROM customer_orders AS o
GROUP BY o.customer_id
ORDER BY orders_count DESC, o.customer_id;

SELECT
    p.category,
    COUNT(*) AS products_count,
    AVG(p.price) AS average_price
FROM products AS p
GROUP BY p.category
ORDER BY average_price DESC;

-- =========================================================
-- 6. Запросы с агрегатными функциями, функциями даты и строковыми функциями, 5 запросов
-- =========================================================

SELECT COUNT(*) AS active_customers_count
FROM customers
WHERE is_active = TRUE;

SELECT
    o.order_id,
    SUM(oi.line_amount) AS order_amount
FROM customer_orders AS o
JOIN order_items AS oi ON oi.order_id = o.order_id
GROUP BY o.order_id
ORDER BY o.order_id;

SELECT
    AVG(quantity_defective) AS avg_defective_qty,
    MIN(production_date) AS first_production_at,
    MAX(production_date) AS last_production_at
FROM production_batches;

SELECT
    DATE_TRUNC('month', order_date) AS order_month,
    EXTRACT(YEAR FROM order_date) AS order_year,
    COUNT(*) AS orders_count
FROM customer_orders
GROUP BY DATE_TRUNC('month', order_date), EXTRACT(YEAR FROM order_date)
ORDER BY order_month;

SELECT
    customer_id,
    CONCAT(UPPER(COALESCE(company_name, full_name)), ' / ', LOWER(COALESCE(email, 'no-email'))) AS customer_label,
    LENGTH(COALESCE(delivery_address, '')) AS address_length,
    CURRENT_DATE AS check_date
FROM customers
ORDER BY customer_id;

-- =========================================================
-- 7. Предметные проверочные запросы
-- =========================================================

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

-- =========================================================
-- 8. Проверочные запросы по безопасности и аудиту
-- =========================================================

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
ORDER BY al.changed_at DESC, al.audit_id DESC;

SELECT set_config('app.current_user_id', '5', true);

SELECT
    o.order_id,
    o.order_number,
    o.customer_id
FROM customer_orders AS o
ORDER BY o.order_id;

SELECT set_config('app.current_user_id', '', true);
