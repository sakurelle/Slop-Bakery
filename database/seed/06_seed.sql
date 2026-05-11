INSERT INTO order_statuses (status_code, name, description) VALUES
    ('draft', 'Draft', 'Order has been created but not yet confirmed.'),
    ('confirmed', 'Confirmed', 'Order has been confirmed by the bakery.'),
    ('in_production', 'In Production', 'Order is being prepared for production.'),
    ('ready', 'Ready', 'Order is ready for shipment.'),
    ('shipped', 'Shipped', 'Order has been shipped to the customer.'),
    ('completed', 'Completed', 'Order has been completed and closed.'),
    ('cancelled', 'Cancelled', 'Order has been cancelled.');

INSERT INTO invoice_statuses (status_code, name, description) VALUES
    ('issued', 'Issued', 'Invoice has been issued.'),
    ('paid', 'Paid', 'Invoice has been paid.'),
    ('overdue', 'Overdue', 'Invoice payment is overdue.'),
    ('cancelled', 'Cancelled', 'Invoice has been cancelled.');

INSERT INTO shipment_statuses (status_code, name, description) VALUES
    ('planned', 'Planned', 'Shipment has been planned.'),
    ('shipped', 'Shipped', 'Shipment has been sent.'),
    ('delivered', 'Delivered', 'Shipment has been delivered.'),
    ('cancelled', 'Cancelled', 'Shipment has been cancelled.');

INSERT INTO delivery_statuses (status_code, name, description) VALUES
    ('planned', 'Planned', 'Delivery has been planned.'),
    ('received', 'Received', 'Delivery has been physically received.'),
    ('accepted', 'Accepted', 'Delivery has passed acceptance.'),
    ('rejected', 'Rejected', 'Delivery has been rejected.'),
    ('cancelled', 'Cancelled', 'Delivery has been cancelled.');

INSERT INTO production_statuses (status_code, name, description) VALUES
    ('planned', 'Planned', 'Production batch has been planned.'),
    ('in_progress', 'In Progress', 'Production is in progress.'),
    ('completed', 'Completed', 'Production batch is completed.'),
    ('rejected', 'Rejected', 'Production batch has been rejected.');

INSERT INTO quality_statuses (status_code, name, description) VALUES
    ('passed', 'Passed', 'Quality check passed.'),
    ('failed', 'Failed', 'Quality check failed.'),
    ('conditional', 'Conditional', 'Quality check passed with remarks.');

INSERT INTO tech_card_statuses (status_code, name, description) VALUES
    ('draft', 'Draft', 'Tech card is being prepared.'),
    ('active', 'Active', 'Tech card is active and approved for use.'),
    ('archived', 'Archived', 'Tech card is archived.');

INSERT INTO user_statuses (status_code, name, description) VALUES
    ('active', 'Active', 'User account is active.'),
    ('blocked', 'Blocked', 'User account is temporarily blocked.'),
    ('disabled', 'Disabled', 'User account is disabled.');

INSERT INTO customers (
    customer_id, customer_type, full_name, company_name, phone, email, delivery_address, created_at, is_active
) VALUES
    (1, 'individual', 'Ivan Petrov', NULL, '+7-900-100-10-10', 'ivan.petrov@example.com', 'Moscow, 12 Baker Street', '2026-03-15 10:00:00+03', TRUE),
    (2, 'company', NULL, 'Sunrise Retail LLC', '+7-900-200-20-20', 'procurement@sunrise-retail.example', 'Moscow, 45 Market Avenue', '2026-03-16 11:30:00+03', TRUE),
    (3, 'individual', 'Anna Sokolova', NULL, '+7-900-300-30-30', NULL, 'Moscow, 78 River Lane', '2026-03-20 09:45:00+03', TRUE);

INSERT INTO suppliers (
    supplier_id, company_name, contact_person, phone, email, address, created_at, is_active
) VALUES
    (1, 'Grain Supply Ltd', 'Sergey Makarov', '+7-901-100-00-01', 'sales@grainsupply.example', 'Tula, 5 Mill Road', '2026-03-10 08:00:00+03', TRUE),
    (2, 'Sweet Ingredients LLC', 'Olga Voronina', '+7-901-200-00-02', 'orders@sweetingredients.example', 'Ryazan, 11 Sugar Park', '2026-03-11 08:15:00+03', TRUE),
    (3, 'Dairy and Oils JSC', 'Nikolay Smirnov', '+7-901-300-00-03', 'office@dairyoils.example', 'Kaluga, 25 Cream Boulevard', '2026-03-12 08:30:00+03', TRUE);

INSERT INTO raw_materials (
    material_id, name, unit, min_stock_qty, shelf_life_days, storage_conditions, is_active
) VALUES
    (1, 'Flour', 'kg', 500.000, 180, 'Store in a dry ventilated warehouse.', TRUE),
    (2, 'Yeast', 'kg', 50.000, 30, 'Keep refrigerated at stable temperature.', TRUE),
    (3, 'Salt', 'kg', 25.000, 365, 'Store in sealed containers.', TRUE),
    (4, 'Sugar', 'kg', 100.000, 365, 'Store in a dry room away from moisture.', TRUE),
    (5, 'Poppy Seeds', 'kg', 40.000, 180, 'Store in sealed food-grade packaging.', TRUE),
    (6, 'Butter', 'kg', 60.000, 60, 'Keep refrigerated at 2-6 C.', TRUE);

INSERT INTO products (
    product_id, name, category, unit, price, shelf_life_days, is_active, created_at
) VALUES
    (1, 'Borodinsky Bread', 'Bread', 'piece', 85.00, 5, TRUE, '2026-03-18 09:00:00+03'),
    (2, 'Moscow Bread', 'Bread', 'piece', 78.00, 4, TRUE, '2026-03-18 09:10:00+03'),
    (3, 'Poppy Seed Roll', 'Pastry', 'piece', 140.00, 4, TRUE, '2026-03-18 09:20:00+03');

INSERT INTO roles (role_id, role_code, role_name, description) VALUES
    (1, 'admin', 'Administrator', 'Full administrative role.'),
    (2, 'technologist', 'Technologist', 'Responsible for tech cards and production planning.'),
    (3, 'warehouse_worker', 'Warehouse Worker', 'Responsible for warehouse operations.'),
    (4, 'quality_control', 'Quality Control', 'Responsible for quality inspection.'),
    (5, 'client', 'Client', 'Customer-facing role.');

INSERT INTO users (
    user_id, username, password_hash, full_name, email, phone, status_code, customer_id, created_at, last_login_at
) VALUES
    (1, 'admin', crypt('admin123', gen_salt('bf', 12)), 'Alexey Morozov', 'admin@bakery.example', '+7-902-100-10-10', 'active', NULL, '2026-03-15 08:00:00+03', NULL);

SELECT set_config('app.current_user_id', '1', false);
SELECT set_config('app.current_user_ip', '192.168.10.10', false);

INSERT INTO users (
    user_id, username, password_hash, full_name, email, phone, status_code, customer_id, created_at, last_login_at
) VALUES
    (2, 'technologist', crypt('tech123', gen_salt('bf', 12)), 'Elena Kuznetsova', 'technologist@bakery.example', '+7-902-200-20-20', 'active', NULL, '2026-03-15 08:05:00+03', NULL),
    (3, 'warehouse', crypt('warehouse123', gen_salt('bf', 12)), 'Pavel Lebedev', 'warehouse@bakery.example', '+7-902-300-30-30', 'active', NULL, '2026-03-15 08:10:00+03', NULL),
    (4, 'quality', crypt('quality123', gen_salt('bf', 12)), 'Maria Volkova', 'quality@bakery.example', '+7-902-400-40-40', 'active', NULL, '2026-03-15 08:15:00+03', NULL),
    (5, 'client', crypt('client123', gen_salt('bf', 12)), 'Ivan Petrov', 'client@bakery.example', '+7-902-500-50-50', 'active', 1, '2026-03-15 08:20:00+03', NULL);

INSERT INTO user_roles (user_id, role_id, assigned_at, assigned_by_user_id) VALUES
    (1, 1, '2026-03-15 08:30:00+03', 1),
    (2, 2, '2026-03-15 08:31:00+03', 1),
    (3, 3, '2026-03-15 08:32:00+03', 1),
    (4, 4, '2026-03-15 08:33:00+03', 1),
    (5, 5, '2026-03-15 08:34:00+03', 1);

INSERT INTO role_permissions (
    permission_id, role_id, object_name, can_select, can_insert, can_update, can_delete
) VALUES
    (1, 1, 'users', TRUE, TRUE, TRUE, TRUE),
    (2, 1, 'audit_log', TRUE, FALSE, FALSE, FALSE),
    (3, 2, 'tech_cards', TRUE, TRUE, TRUE, FALSE),
    (4, 2, 'recipe_items', TRUE, TRUE, TRUE, FALSE),
    (5, 2, 'production_batches', TRUE, TRUE, TRUE, FALSE),
    (6, 3, 'raw_material_deliveries', TRUE, TRUE, TRUE, FALSE),
    (7, 3, 'raw_material_stock', TRUE, TRUE, TRUE, FALSE),
    (8, 3, 'shipments', TRUE, TRUE, TRUE, FALSE),
    (9, 4, 'quality_checks', TRUE, TRUE, TRUE, FALSE),
    (10, 5, 'customer_orders', TRUE, FALSE, FALSE, FALSE),
    (11, 5, 'invoices', TRUE, FALSE, FALSE, FALSE),
    (12, 5, 'shipments', TRUE, FALSE, FALSE, FALSE);

INSERT INTO supplier_materials (
    supplier_material_id, supplier_id, material_id, purchase_price, lead_time_days, is_active
) VALUES
    (1, 1, 1, 18.00, 2, TRUE),
    (2, 1, 3, 9.00, 2, TRUE),
    (3, 1, 2, 190.00, 3, TRUE),
    (4, 2, 4, 52.00, 3, TRUE),
    (5, 2, 5, 240.00, 4, TRUE),
    (6, 2, 1, 19.00, 4, TRUE),
    (7, 3, 2, 185.00, 1, TRUE),
    (8, 3, 6, 310.00, 1, TRUE);

INSERT INTO raw_material_deliveries (
    delivery_id, supplier_id, delivery_number, delivery_date, status_code, received_by_user_id, document_ref, total_amount, note
) VALUES
    (1, 1, 'DN-2026-001', '2026-03-25', 'accepted', 3, 'SUP-INV-001', 22950.00, 'Main flour and salt delivery.'),
    (2, 2, 'DN-2026-002', '2026-03-27', 'accepted', 3, 'SUP-INV-002', 49600.00, 'Sugar and poppy seeds delivery.'),
    (3, 3, 'DN-2026-003', '2026-04-01', 'accepted', 3, 'SUP-INV-003', 72450.00, 'Yeast and butter delivery.');

INSERT INTO delivery_items (
    delivery_item_id, delivery_id, material_id, quantity, unit_price, batch_number, expiry_date
) VALUES
    (1, 1, 1, 1200.000, 18.00, 'FL-260325', '2026-09-21'),
    (2, 1, 3, 150.000, 9.00, 'SA-260325', '2027-03-25'),
    (3, 2, 4, 400.000, 52.00, 'SU-260327', '2027-03-27'),
    (4, 2, 5, 120.000, 240.00, 'PO-260327', '2026-09-27'),
    (5, 3, 2, 90.000, 185.00, 'YE-260401', '2026-04-25'),
    (6, 3, 6, 180.000, 310.00, 'BU-260401', '2026-05-10');

INSERT INTO raw_material_stock (
    stock_id, material_id, delivery_item_id, batch_number, quantity_current, expiry_date, updated_at
) VALUES
    (1, 1, 1, 'FL-260325', 860.000, '2026-09-21', '2026-04-06 18:00:00+03'),
    (2, 3, 2, 'SA-260325', 120.000, '2027-03-25', '2026-04-06 18:01:00+03'),
    (3, 4, 3, 'SU-260327', 260.000, '2027-03-27', '2026-04-06 18:02:00+03'),
    (4, 5, 4, 'PO-260327', 70.000, '2026-09-27', '2026-04-06 18:03:00+03'),
    (5, 2, 5, 'YE-260401', 35.000, '2026-04-25', '2026-04-06 18:04:00+03'),
    (6, 6, 6, 'BU-260401', 90.000, '2026-05-10', '2026-04-06 18:05:00+03');

INSERT INTO tech_cards (
    tech_card_id, product_id, card_number, version, status_code, effective_from, effective_to,
    baking_time_min, baking_temperature_c, process_description, approved_by_user_id
) VALUES
    (1, 1, 'TC-BREAD-001', 1, 'active', '2026-01-01', NULL, 48, 225.00, 'Mix rye dough, proof, bake and cool on racks.', 2),
    (2, 2, 'TC-BREAD-002', 1, 'active', '2026-01-01', NULL, 42, 220.00, 'Prepare wheat dough, ferment, shape and bake.', 2),
    (3, 3, 'TC-ROLL-001', 1, 'active', '2026-01-01', NULL, 32, 210.00, 'Prepare sweet dough, add filling, roll, proof and bake.', 2);

INSERT INTO recipe_items (
    recipe_item_id, tech_card_id, material_id, quantity, unit, stage, waste_percent, note
) VALUES
    (1, 1, 1, 0.700, 'kg', 'mixing', 1.50, 'Base flour for borodinsky bread.'),
    (2, 1, 2, 0.020, 'kg', 'mixing', 0.00, 'Pressed yeast.'),
    (3, 1, 3, 0.015, 'kg', 'mixing', 0.00, 'Salt for dough balance.'),
    (4, 1, 4, 0.030, 'kg', 'mixing', 0.00, 'Sugar for fermentation support.'),
    (5, 2, 1, 0.650, 'kg', 'mixing', 1.20, 'Base flour for moscow bread.'),
    (6, 2, 2, 0.018, 'kg', 'mixing', 0.00, 'Pressed yeast.'),
    (7, 2, 3, 0.012, 'kg', 'mixing', 0.00, 'Salt for dough balance.'),
    (8, 2, 6, 0.015, 'kg', 'finishing', 0.50, 'Butter for crust softness.'),
    (9, 3, 1, 0.500, 'kg', 'mixing', 1.00, 'Base flour for sweet dough.'),
    (10, 3, 2, 0.015, 'kg', 'mixing', 0.00, 'Pressed yeast.'),
    (11, 3, 4, 0.080, 'kg', 'mixing', 0.00, 'Sugar for sweet dough.'),
    (12, 3, 6, 0.060, 'kg', 'mixing', 0.50, 'Butter for layered texture.'),
    (13, 3, 5, 0.120, 'kg', 'filling', 2.00, 'Poppy seed filling.'),
    (14, 3, 3, 0.008, 'kg', 'mixing', 0.00, 'Salt for flavor balance.');

INSERT INTO customer_orders (
    order_id, order_number, customer_id, order_date, planned_shipment_date, status_code, created_by_user_id, comment
) VALUES
    (1, 'ORD-2026-001', 1, '2026-04-02 09:15:00+03', '2026-04-03', 'completed', 5, 'Retail order for family event.'),
    (2, 'ORD-2026-002', 2, '2026-04-04 10:00:00+03', '2026-04-06', 'shipped', 1, 'Weekly store replenishment.'),
    (3, 'ORD-2026-003', 3, '2026-04-06 14:30:00+03', '2026-04-07', 'confirmed', 1, 'Advance pastry order.');

INSERT INTO order_items (
    order_item_id, order_id, product_id, quantity, unit_price, line_amount
) VALUES
    (1, 1, 1, 40.000, 85.00, 3400.00),
    (2, 1, 3, 10.000, 140.00, 1400.00),
    (3, 2, 2, 80.000, 78.00, 6240.00),
    (4, 2, 1, 50.000, 85.00, 4250.00),
    (5, 3, 3, 12.000, 140.00, 1680.00);

INSERT INTO production_batches (
    production_batch_id, batch_number, product_id, tech_card_id, production_date, shift,
    quantity_produced, quantity_defective, responsible_user_id, status_code, note
) VALUES
    (1, 'PB-2026-0402-01', 1, 1, '2026-04-02 04:00:00+03', 'morning', 120.000, 2.000, 2, 'completed', 'Planned batch for customer orders 1 and 2.'),
    (2, 'PB-2026-0404-01', 2, 2, '2026-04-04 04:30:00+03', 'morning', 100.000, 1.000, 2, 'completed', 'Batch produced for wholesale client order.'),
    (3, 'PB-2026-0406-01', 3, 3, '2026-04-06 05:00:00+03', 'morning', 40.000, 0.000, 2, 'completed', 'Batch produced for retail roll orders.');

INSERT INTO finished_goods_stock (
    finished_stock_id, product_id, production_batch_id, batch_number, quantity_current,
    production_date, expiry_date, updated_at
) VALUES
    (1, 1, 1, 'PB-2026-0402-01', 28.000, '2026-04-02', '2026-04-07', '2026-04-06 18:10:00+03'),
    (2, 2, 2, 'PB-2026-0404-01', 20.000, '2026-04-04', '2026-04-08', '2026-04-06 18:11:00+03'),
    (3, 3, 3, 'PB-2026-0406-01', 30.000, '2026-04-06', '2026-04-10', '2026-04-06 18:12:00+03');

INSERT INTO quality_checks (
    quality_check_id, check_type, delivery_item_id, production_batch_id, checked_at,
    inspector_user_id, result_code, parameter_name, measured_value, standard_value, document_number, note
) VALUES
    (1, 'raw_material', 1, NULL, '2026-03-25 14:00:00+03', 4, 'passed', 'moisture', '14.0%', '<= 15.0%', 'QC-RM-001', 'Flour batch accepted.'),
    (2, 'raw_material', 5, NULL, '2026-04-01 13:00:00+03', 4, 'conditional', 'fermentation_activity', '82%', '>= 80%', 'QC-RM-002', 'Yeast accepted with note for accelerated usage.'),
    (3, 'finished_product', NULL, 1, '2026-04-02 07:30:00+03', 4, 'passed', 'weight', '0.78 kg', '0.75-0.80 kg', 'QC-FG-001', 'Borodinsky bread batch meets standard.'),
    (4, 'finished_product', NULL, 3, '2026-04-06 08:20:00+03', 4, 'passed', 'filling_distribution', 'uniform', 'even distribution', 'QC-FG-002', 'Roll filling distribution is acceptable.');

INSERT INTO invoices (
    invoice_id, invoice_number, order_id, issue_date, due_date, paid_at, amount, status_code, note
) VALUES
    (1, 'INV-2026-001', 1, '2026-04-02', '2026-04-05', '2026-04-03 12:00:00+03', 4800.00, 'paid', 'Paid immediately after shipment.'),
    (2, 'INV-2026-002', 2, '2026-04-04', '2026-04-10', NULL, 10490.00, 'issued', 'Wholesale invoice awaiting payment.'),
    (3, 'INV-2026-003', 3, '2026-04-06', '2026-04-08', NULL, 1680.00, 'overdue', 'Retail invoice overdue.');

INSERT INTO shipments (
    shipment_id, shipment_number, order_id, shipped_at, status_code, delivery_address, waybill_number, created_by_user_id, note
) VALUES
    (1, 'SHP-2026-001', 1, '2026-04-03 08:00:00+03', 'delivered', 'Moscow, 12 Baker Street', 'WB-2026-001', 3, 'Delivered by local courier.'),
    (2, 'SHP-2026-002', 2, '2026-04-06 09:00:00+03', 'shipped', 'Moscow, 45 Market Avenue', 'WB-2026-002', 3, 'Wholesale delivery in transit.'),
    (3, 'SHP-2026-003', 3, NULL, 'planned', 'Moscow, 78 River Lane', NULL, 3, 'Shipment planned for next route window.');

INSERT INTO shipment_items (
    shipment_item_id, shipment_id, order_item_id, product_id, finished_stock_id, quantity
) VALUES
    (1, 1, 1, 1, 1, 40.000),
    (2, 1, 2, 3, 3, 10.000),
    (3, 2, 3, 2, 2, 79.000),
    (4, 2, 4, 1, 1, 50.000);

UPDATE users
SET last_login_at = '2026-04-10 08:00:00+03'
WHERE user_id = 1;

UPDATE users
SET last_login_at = '2026-04-02 09:00:00+03'
WHERE user_id = 5;

SELECT log_auth_event(1, 'LOGIN', '192.168.10.10', TRUE);
SELECT log_auth_event(1, 'LOGOUT', '192.168.10.10', TRUE);
SELECT log_auth_event(5, 'LOGIN', '192.168.10.25', TRUE);

SELECT set_config('app.current_user_id', '', false);
SELECT set_config('app.current_user_ip', '', false);
