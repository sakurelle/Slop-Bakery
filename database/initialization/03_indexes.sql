CREATE INDEX IF NOT EXISTS idx_users_status_code
    ON users (status_code);

CREATE INDEX IF NOT EXISTS idx_users_customer_id
    ON users (customer_id);

CREATE INDEX IF NOT EXISTS idx_role_permissions_role_id
    ON role_permissions (role_id);

CREATE INDEX IF NOT EXISTS idx_user_roles_role_id
    ON user_roles (role_id);

CREATE INDEX IF NOT EXISTS idx_user_roles_assigned_by_user_id
    ON user_roles (assigned_by_user_id);

CREATE INDEX IF NOT EXISTS idx_supplier_materials_supplier_id
    ON supplier_materials (supplier_id);

CREATE INDEX IF NOT EXISTS idx_supplier_materials_material_id
    ON supplier_materials (material_id);

CREATE INDEX IF NOT EXISTS idx_raw_material_deliveries_supplier_id
    ON raw_material_deliveries (supplier_id);

CREATE INDEX IF NOT EXISTS idx_raw_material_deliveries_status_code
    ON raw_material_deliveries (status_code);

CREATE INDEX IF NOT EXISTS idx_raw_material_deliveries_received_by_user_id
    ON raw_material_deliveries (received_by_user_id);

CREATE INDEX IF NOT EXISTS idx_raw_material_deliveries_delivery_date
    ON raw_material_deliveries (delivery_date);

CREATE INDEX IF NOT EXISTS idx_delivery_items_delivery_id
    ON delivery_items (delivery_id);

CREATE INDEX IF NOT EXISTS idx_delivery_items_material_id
    ON delivery_items (material_id);

CREATE INDEX IF NOT EXISTS idx_raw_material_stock_material_id
    ON raw_material_stock (material_id);

CREATE INDEX IF NOT EXISTS idx_raw_material_stock_delivery_item_id
    ON raw_material_stock (delivery_item_id);

CREATE INDEX IF NOT EXISTS idx_raw_material_stock_batch_number
    ON raw_material_stock (batch_number);

CREATE INDEX IF NOT EXISTS idx_tech_cards_product_id
    ON tech_cards (product_id);

CREATE INDEX IF NOT EXISTS idx_tech_cards_status_code
    ON tech_cards (status_code);

CREATE INDEX IF NOT EXISTS idx_tech_cards_approved_by_user_id
    ON tech_cards (approved_by_user_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tech_cards_one_active_per_product
    ON tech_cards (product_id)
    WHERE status_code = 'active';

CREATE INDEX IF NOT EXISTS idx_recipe_items_tech_card_id
    ON recipe_items (tech_card_id);

CREATE INDEX IF NOT EXISTS idx_recipe_items_material_id
    ON recipe_items (material_id);

CREATE INDEX IF NOT EXISTS idx_customer_orders_customer_id
    ON customer_orders (customer_id);

CREATE INDEX IF NOT EXISTS idx_customer_orders_status_code
    ON customer_orders (status_code);

CREATE INDEX IF NOT EXISTS idx_customer_orders_created_by_user_id
    ON customer_orders (created_by_user_id);

CREATE INDEX IF NOT EXISTS idx_customer_orders_order_date
    ON customer_orders (order_date);

CREATE INDEX IF NOT EXISTS idx_order_items_order_id
    ON order_items (order_id);

CREATE INDEX IF NOT EXISTS idx_order_items_product_id
    ON order_items (product_id);

CREATE INDEX IF NOT EXISTS idx_production_batches_product_id
    ON production_batches (product_id);

CREATE INDEX IF NOT EXISTS idx_production_batches_tech_card_id
    ON production_batches (tech_card_id);

CREATE INDEX IF NOT EXISTS idx_production_batches_responsible_user_id
    ON production_batches (responsible_user_id);

CREATE INDEX IF NOT EXISTS idx_production_batches_status_code
    ON production_batches (status_code);

CREATE INDEX IF NOT EXISTS idx_production_batches_production_date
    ON production_batches (production_date);

CREATE INDEX IF NOT EXISTS idx_finished_goods_stock_product_id
    ON finished_goods_stock (product_id);

CREATE INDEX IF NOT EXISTS idx_finished_goods_stock_production_batch_id
    ON finished_goods_stock (production_batch_id);

CREATE INDEX IF NOT EXISTS idx_finished_goods_stock_batch_number
    ON finished_goods_stock (batch_number);

CREATE INDEX IF NOT EXISTS idx_quality_checks_delivery_item_id
    ON quality_checks (delivery_item_id);

CREATE INDEX IF NOT EXISTS idx_quality_checks_production_batch_id
    ON quality_checks (production_batch_id);

CREATE INDEX IF NOT EXISTS idx_quality_checks_inspector_user_id
    ON quality_checks (inspector_user_id);

CREATE INDEX IF NOT EXISTS idx_quality_checks_result_code
    ON quality_checks (result_code);

CREATE INDEX IF NOT EXISTS idx_quality_checks_checked_at
    ON quality_checks (checked_at);

CREATE INDEX IF NOT EXISTS idx_invoices_order_id
    ON invoices (order_id);

CREATE INDEX IF NOT EXISTS idx_invoices_status_code
    ON invoices (status_code);

CREATE INDEX IF NOT EXISTS idx_shipments_order_id
    ON shipments (order_id);

CREATE INDEX IF NOT EXISTS idx_shipments_status_code
    ON shipments (status_code);

CREATE INDEX IF NOT EXISTS idx_shipments_created_by_user_id
    ON shipments (created_by_user_id);

CREATE INDEX IF NOT EXISTS idx_shipments_shipped_at
    ON shipments (shipped_at);

CREATE INDEX IF NOT EXISTS idx_shipment_items_shipment_id
    ON shipment_items (shipment_id);

CREATE INDEX IF NOT EXISTS idx_shipment_items_order_item_product
    ON shipment_items (order_item_id, product_id);

CREATE INDEX IF NOT EXISTS idx_shipment_items_finished_stock_product
    ON shipment_items (finished_stock_id, product_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_user_changed_at
    ON audit_log (user_id, changed_at);

-- Unique constraints uq_products_name and uq_raw_materials_name
-- already create indexes for products.name and raw_materials.name.
