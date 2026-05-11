ALTER TABLE order_statuses
    ALTER COLUMN status_code SET NOT NULL,
    ALTER COLUMN name SET NOT NULL,
    ADD CONSTRAINT uq_order_statuses_name UNIQUE (name),
    ADD CONSTRAINT chk_order_statuses_status_code_not_blank CHECK (BTRIM(status_code) <> ''),
    ADD CONSTRAINT chk_order_statuses_name_not_blank CHECK (BTRIM(name) <> '');

ALTER TABLE invoice_statuses
    ALTER COLUMN status_code SET NOT NULL,
    ALTER COLUMN name SET NOT NULL,
    ADD CONSTRAINT uq_invoice_statuses_name UNIQUE (name),
    ADD CONSTRAINT chk_invoice_statuses_status_code_not_blank CHECK (BTRIM(status_code) <> ''),
    ADD CONSTRAINT chk_invoice_statuses_name_not_blank CHECK (BTRIM(name) <> '');

ALTER TABLE shipment_statuses
    ALTER COLUMN status_code SET NOT NULL,
    ALTER COLUMN name SET NOT NULL,
    ADD CONSTRAINT uq_shipment_statuses_name UNIQUE (name),
    ADD CONSTRAINT chk_shipment_statuses_status_code_not_blank CHECK (BTRIM(status_code) <> ''),
    ADD CONSTRAINT chk_shipment_statuses_name_not_blank CHECK (BTRIM(name) <> '');

ALTER TABLE delivery_statuses
    ALTER COLUMN status_code SET NOT NULL,
    ALTER COLUMN name SET NOT NULL,
    ADD CONSTRAINT uq_delivery_statuses_name UNIQUE (name),
    ADD CONSTRAINT chk_delivery_statuses_status_code_not_blank CHECK (BTRIM(status_code) <> ''),
    ADD CONSTRAINT chk_delivery_statuses_name_not_blank CHECK (BTRIM(name) <> '');

ALTER TABLE production_statuses
    ALTER COLUMN status_code SET NOT NULL,
    ALTER COLUMN name SET NOT NULL,
    ADD CONSTRAINT uq_production_statuses_name UNIQUE (name),
    ADD CONSTRAINT chk_production_statuses_status_code_not_blank CHECK (BTRIM(status_code) <> ''),
    ADD CONSTRAINT chk_production_statuses_name_not_blank CHECK (BTRIM(name) <> '');

ALTER TABLE quality_statuses
    ALTER COLUMN status_code SET NOT NULL,
    ALTER COLUMN name SET NOT NULL,
    ADD CONSTRAINT uq_quality_statuses_name UNIQUE (name),
    ADD CONSTRAINT chk_quality_statuses_status_code_not_blank CHECK (BTRIM(status_code) <> ''),
    ADD CONSTRAINT chk_quality_statuses_name_not_blank CHECK (BTRIM(name) <> '');

ALTER TABLE tech_card_statuses
    ALTER COLUMN status_code SET NOT NULL,
    ALTER COLUMN name SET NOT NULL,
    ADD CONSTRAINT uq_tech_card_statuses_name UNIQUE (name),
    ADD CONSTRAINT chk_tech_card_statuses_status_code_not_blank CHECK (BTRIM(status_code) <> ''),
    ADD CONSTRAINT chk_tech_card_statuses_name_not_blank CHECK (BTRIM(name) <> '');

ALTER TABLE user_statuses
    ALTER COLUMN status_code SET NOT NULL,
    ALTER COLUMN name SET NOT NULL,
    ADD CONSTRAINT uq_user_statuses_name UNIQUE (name),
    ADD CONSTRAINT chk_user_statuses_status_code_not_blank CHECK (BTRIM(status_code) <> ''),
    ADD CONSTRAINT chk_user_statuses_name_not_blank CHECK (BTRIM(name) <> '');

ALTER TABLE customers
    ALTER COLUMN customer_type SET NOT NULL,
    ALTER COLUMN phone SET NOT NULL,
    ALTER COLUMN delivery_address SET NOT NULL,
    ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN is_active SET DEFAULT TRUE,
    ADD CONSTRAINT uq_customers_email UNIQUE (email),
    ADD CONSTRAINT chk_customers_type CHECK (customer_type IN ('individual', 'company')),
    ADD CONSTRAINT chk_customers_phone_not_blank CHECK (BTRIM(phone) <> ''),
    ADD CONSTRAINT chk_customers_delivery_address_not_blank CHECK (BTRIM(delivery_address) <> ''),
    ADD CONSTRAINT chk_customers_full_name_required CHECK (
        customer_type <> 'individual' OR NULLIF(BTRIM(full_name), '') IS NOT NULL
    ),
    ADD CONSTRAINT chk_customers_company_name_required CHECK (
        customer_type <> 'company' OR NULLIF(BTRIM(company_name), '') IS NOT NULL
    );

ALTER TABLE suppliers
    ALTER COLUMN company_name SET NOT NULL,
    ALTER COLUMN phone SET NOT NULL,
    ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN is_active SET DEFAULT TRUE,
    ADD CONSTRAINT uq_suppliers_company_name UNIQUE (company_name),
    ADD CONSTRAINT uq_suppliers_email UNIQUE (email),
    ADD CONSTRAINT chk_suppliers_company_name_not_blank CHECK (BTRIM(company_name) <> ''),
    ADD CONSTRAINT chk_suppliers_phone_not_blank CHECK (BTRIM(phone) <> '');

ALTER TABLE raw_materials
    ALTER COLUMN name SET NOT NULL,
    ALTER COLUMN unit SET NOT NULL,
    ALTER COLUMN min_stock_qty SET NOT NULL,
    ALTER COLUMN min_stock_qty SET DEFAULT 0,
    ALTER COLUMN is_active SET DEFAULT TRUE,
    ADD CONSTRAINT uq_raw_materials_name UNIQUE (name),
    ADD CONSTRAINT chk_raw_materials_name_not_blank CHECK (BTRIM(name) <> ''),
    ADD CONSTRAINT chk_raw_materials_unit_not_blank CHECK (BTRIM(unit) <> ''),
    ADD CONSTRAINT chk_raw_materials_min_stock_qty CHECK (min_stock_qty >= 0),
    ADD CONSTRAINT chk_raw_materials_shelf_life_days CHECK (shelf_life_days IS NULL OR shelf_life_days > 0);

ALTER TABLE users
    ALTER COLUMN username SET NOT NULL,
    ALTER COLUMN password_hash SET NOT NULL,
    ALTER COLUMN full_name SET NOT NULL,
    ALTER COLUMN status_code SET NOT NULL,
    ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
    ADD CONSTRAINT uq_users_username UNIQUE (username),
    ADD CONSTRAINT uq_users_email UNIQUE (email),
    ADD CONSTRAINT chk_users_username_not_blank CHECK (BTRIM(username) <> ''),
    ADD CONSTRAINT chk_users_password_hash_not_blank CHECK (BTRIM(password_hash) <> ''),
    ADD CONSTRAINT chk_users_full_name_not_blank CHECK (BTRIM(full_name) <> '');

ALTER TABLE roles
    ALTER COLUMN role_code SET NOT NULL,
    ALTER COLUMN role_name SET NOT NULL,
    ADD CONSTRAINT uq_roles_role_code UNIQUE (role_code),
    ADD CONSTRAINT uq_roles_role_name UNIQUE (role_name),
    ADD CONSTRAINT chk_roles_role_code_not_blank CHECK (BTRIM(role_code) <> ''),
    ADD CONSTRAINT chk_roles_role_name_not_blank CHECK (BTRIM(role_name) <> '');

ALTER TABLE role_permissions
    ALTER COLUMN role_id SET NOT NULL,
    ALTER COLUMN object_name SET NOT NULL,
    ALTER COLUMN can_select SET DEFAULT FALSE,
    ALTER COLUMN can_insert SET DEFAULT FALSE,
    ALTER COLUMN can_update SET DEFAULT FALSE,
    ALTER COLUMN can_delete SET DEFAULT FALSE,
    ADD CONSTRAINT uq_role_permissions_role_object UNIQUE (role_id, object_name),
    ADD CONSTRAINT chk_role_permissions_object_name_not_blank CHECK (BTRIM(object_name) <> '');

ALTER TABLE user_roles
    ALTER COLUMN user_id SET NOT NULL,
    ALTER COLUMN role_id SET NOT NULL,
    ALTER COLUMN assigned_at SET DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE supplier_materials
    ALTER COLUMN supplier_id SET NOT NULL,
    ALTER COLUMN material_id SET NOT NULL,
    ALTER COLUMN is_active SET DEFAULT TRUE,
    ADD CONSTRAINT uq_supplier_materials_supplier_material UNIQUE (supplier_id, material_id),
    ADD CONSTRAINT chk_supplier_materials_purchase_price CHECK (purchase_price IS NULL OR purchase_price >= 0),
    ADD CONSTRAINT chk_supplier_materials_lead_time_days CHECK (lead_time_days IS NULL OR lead_time_days >= 0);

ALTER TABLE raw_material_deliveries
    ALTER COLUMN supplier_id SET NOT NULL,
    ALTER COLUMN delivery_number SET NOT NULL,
    ALTER COLUMN delivery_date SET NOT NULL,
    ALTER COLUMN status_code SET NOT NULL,
    ALTER COLUMN delivery_date SET DEFAULT CURRENT_DATE,
    ALTER COLUMN total_amount SET DEFAULT 0,
    ADD CONSTRAINT uq_raw_material_deliveries_number UNIQUE (delivery_number),
    ADD CONSTRAINT chk_raw_material_deliveries_number_not_blank CHECK (BTRIM(delivery_number) <> ''),
    ADD CONSTRAINT chk_raw_material_deliveries_total_amount CHECK (total_amount >= 0);

ALTER TABLE delivery_items
    ALTER COLUMN delivery_id SET NOT NULL,
    ALTER COLUMN material_id SET NOT NULL,
    ALTER COLUMN quantity SET NOT NULL,
    ALTER COLUMN unit_price SET NOT NULL,
    ALTER COLUMN expiry_date SET NOT NULL,
    ADD CONSTRAINT uq_delivery_items_delivery_material_batch UNIQUE NULLS NOT DISTINCT (delivery_id, material_id, batch_number),
    ADD CONSTRAINT uq_delivery_items_item_material UNIQUE (delivery_item_id, material_id),
    ADD CONSTRAINT chk_delivery_items_quantity CHECK (quantity > 0),
    ADD CONSTRAINT chk_delivery_items_unit_price CHECK (unit_price >= 0),
    ADD CONSTRAINT chk_delivery_items_batch_number_not_blank CHECK (batch_number IS NULL OR BTRIM(batch_number) <> '');

ALTER TABLE raw_material_stock
    ALTER COLUMN material_id SET NOT NULL,
    ALTER COLUMN quantity_current SET NOT NULL,
    ALTER COLUMN expiry_date SET NOT NULL,
    ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP,
    ADD CONSTRAINT uq_raw_material_stock_material_batch UNIQUE NULLS NOT DISTINCT (material_id, batch_number),
    ADD CONSTRAINT chk_raw_material_stock_quantity_current CHECK (quantity_current >= 0),
    ADD CONSTRAINT chk_raw_material_stock_batch_number_not_blank CHECK (batch_number IS NULL OR BTRIM(batch_number) <> '');

ALTER TABLE products
    ALTER COLUMN name SET NOT NULL,
    ALTER COLUMN unit SET NOT NULL,
    ALTER COLUMN price SET NOT NULL,
    ALTER COLUMN shelf_life_days SET NOT NULL,
    ALTER COLUMN is_active SET DEFAULT TRUE,
    ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
    ADD CONSTRAINT uq_products_name UNIQUE (name),
    ADD CONSTRAINT chk_products_name_not_blank CHECK (BTRIM(name) <> ''),
    ADD CONSTRAINT chk_products_unit_not_blank CHECK (BTRIM(unit) <> ''),
    ADD CONSTRAINT chk_products_price CHECK (price >= 0),
    ADD CONSTRAINT chk_products_shelf_life_days CHECK (shelf_life_days > 0);

ALTER TABLE tech_cards
    ALTER COLUMN product_id SET NOT NULL,
    ALTER COLUMN card_number SET NOT NULL,
    ALTER COLUMN version SET NOT NULL,
    ALTER COLUMN status_code SET NOT NULL,
    ALTER COLUMN effective_from SET NOT NULL,
    ALTER COLUMN baking_time_min SET NOT NULL,
    ALTER COLUMN baking_temperature_c SET NOT NULL,
    ALTER COLUMN process_description SET NOT NULL,
    ADD CONSTRAINT uq_tech_cards_card_number UNIQUE (card_number),
    ADD CONSTRAINT uq_tech_cards_product_version UNIQUE (product_id, version),
    ADD CONSTRAINT uq_tech_cards_card_product UNIQUE (tech_card_id, product_id),
    ADD CONSTRAINT chk_tech_cards_card_number_not_blank CHECK (BTRIM(card_number) <> ''),
    ADD CONSTRAINT chk_tech_cards_version CHECK (version > 0),
    ADD CONSTRAINT chk_tech_cards_baking_time_min CHECK (baking_time_min > 0),
    ADD CONSTRAINT chk_tech_cards_baking_temperature CHECK (baking_temperature_c > 0),
    ADD CONSTRAINT chk_tech_cards_process_description_not_blank CHECK (BTRIM(process_description) <> ''),
    ADD CONSTRAINT chk_tech_cards_effective_to CHECK (effective_to IS NULL OR effective_to > effective_from);

ALTER TABLE recipe_items
    ALTER COLUMN tech_card_id SET NOT NULL,
    ALTER COLUMN material_id SET NOT NULL,
    ALTER COLUMN quantity SET NOT NULL,
    ALTER COLUMN unit SET NOT NULL,
    ALTER COLUMN waste_percent SET DEFAULT 0,
    ADD CONSTRAINT uq_recipe_items_card_material_stage UNIQUE NULLS NOT DISTINCT (tech_card_id, material_id, stage),
    ADD CONSTRAINT chk_recipe_items_quantity CHECK (quantity > 0),
    ADD CONSTRAINT chk_recipe_items_unit_not_blank CHECK (BTRIM(unit) <> ''),
    ADD CONSTRAINT chk_recipe_items_stage_not_blank CHECK (stage IS NULL OR BTRIM(stage) <> ''),
    ADD CONSTRAINT chk_recipe_items_waste_percent CHECK (waste_percent >= 0 AND waste_percent < 100);

ALTER TABLE customer_orders
    ALTER COLUMN order_number SET NOT NULL,
    ALTER COLUMN customer_id SET NOT NULL,
    ALTER COLUMN status_code SET NOT NULL,
    ALTER COLUMN order_date SET DEFAULT CURRENT_TIMESTAMP,
    ADD CONSTRAINT uq_customer_orders_number UNIQUE (order_number),
    ADD CONSTRAINT chk_customer_orders_number_not_blank CHECK (BTRIM(order_number) <> ''),
    ADD CONSTRAINT chk_customer_orders_planned_shipment_date CHECK (
        planned_shipment_date IS NULL OR planned_shipment_date >= order_date::DATE
    );

ALTER TABLE order_items
    ALTER COLUMN order_id SET NOT NULL,
    ALTER COLUMN product_id SET NOT NULL,
    ALTER COLUMN quantity SET NOT NULL,
    ALTER COLUMN unit_price SET NOT NULL,
    ADD CONSTRAINT uq_order_items_order_product UNIQUE (order_id, product_id),
    ADD CONSTRAINT uq_order_items_item_product UNIQUE (order_item_id, product_id),
    ADD CONSTRAINT chk_order_items_quantity CHECK (quantity > 0),
    ADD CONSTRAINT chk_order_items_unit_price CHECK (unit_price >= 0),
    ADD CONSTRAINT chk_order_items_line_amount CHECK (line_amount IS NULL OR line_amount >= 0);

ALTER TABLE production_batches
    ALTER COLUMN batch_number SET NOT NULL,
    ALTER COLUMN product_id SET NOT NULL,
    ALTER COLUMN tech_card_id SET NOT NULL,
    ALTER COLUMN production_date SET NOT NULL,
    ALTER COLUMN quantity_produced SET NOT NULL,
    ALTER COLUMN status_code SET NOT NULL,
    ALTER COLUMN production_date SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN quantity_defective SET DEFAULT 0,
    ADD CONSTRAINT uq_production_batches_batch_number UNIQUE (batch_number),
    ADD CONSTRAINT uq_production_batches_batch_product UNIQUE (production_batch_id, product_id),
    ADD CONSTRAINT chk_production_batches_batch_number_not_blank CHECK (BTRIM(batch_number) <> ''),
    ADD CONSTRAINT chk_production_batches_shift_not_blank CHECK (shift IS NULL OR BTRIM(shift) <> ''),
    ADD CONSTRAINT chk_production_batches_quantity_produced CHECK (quantity_produced > 0),
    ADD CONSTRAINT chk_production_batches_quantity_defective CHECK (
        quantity_defective >= 0 AND quantity_defective <= quantity_produced
    );

ALTER TABLE finished_goods_stock
    ALTER COLUMN product_id SET NOT NULL,
    ALTER COLUMN production_batch_id SET NOT NULL,
    ALTER COLUMN batch_number SET NOT NULL,
    ALTER COLUMN quantity_current SET NOT NULL,
    ALTER COLUMN production_date SET NOT NULL,
    ALTER COLUMN expiry_date SET NOT NULL,
    ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP,
    ADD CONSTRAINT uq_finished_goods_stock_product_batch UNIQUE (product_id, batch_number),
    ADD CONSTRAINT uq_finished_goods_stock_item_product UNIQUE (finished_stock_id, product_id),
    ADD CONSTRAINT chk_finished_goods_stock_batch_number_not_blank CHECK (BTRIM(batch_number) <> ''),
    ADD CONSTRAINT chk_finished_goods_stock_quantity_current CHECK (quantity_current >= 0),
    ADD CONSTRAINT chk_finished_goods_stock_expiry_date CHECK (expiry_date > production_date);

ALTER TABLE quality_checks
    ALTER COLUMN check_type SET NOT NULL,
    ALTER COLUMN result_code SET NOT NULL,
    ALTER COLUMN checked_at SET DEFAULT CURRENT_TIMESTAMP,
    ADD CONSTRAINT uq_quality_checks_document_number UNIQUE (document_number),
    ADD CONSTRAINT chk_quality_checks_type CHECK (check_type IN ('raw_material', 'finished_product')),
    ADD CONSTRAINT chk_quality_checks_reference CHECK (
        (check_type = 'raw_material' AND delivery_item_id IS NOT NULL AND production_batch_id IS NULL)
        OR
        (check_type = 'finished_product' AND production_batch_id IS NOT NULL AND delivery_item_id IS NULL)
    ),
    ADD CONSTRAINT chk_quality_checks_document_number_not_blank CHECK (
        document_number IS NULL OR BTRIM(document_number) <> ''
    );

ALTER TABLE invoices
    ALTER COLUMN invoice_number SET NOT NULL,
    ALTER COLUMN order_id SET NOT NULL,
    ALTER COLUMN issue_date SET NOT NULL,
    ALTER COLUMN amount SET NOT NULL,
    ALTER COLUMN status_code SET NOT NULL,
    ALTER COLUMN issue_date SET DEFAULT CURRENT_DATE,
    ADD CONSTRAINT uq_invoices_number UNIQUE (invoice_number),
    ADD CONSTRAINT chk_invoices_number_not_blank CHECK (BTRIM(invoice_number) <> ''),
    ADD CONSTRAINT chk_invoices_amount CHECK (amount >= 0),
    ADD CONSTRAINT chk_invoices_due_date CHECK (due_date IS NULL OR due_date >= issue_date),
    ADD CONSTRAINT chk_invoices_paid_at CHECK (paid_at IS NULL OR paid_at::DATE >= issue_date);

ALTER TABLE shipments
    ALTER COLUMN shipment_number SET NOT NULL,
    ALTER COLUMN order_id SET NOT NULL,
    ALTER COLUMN status_code SET NOT NULL,
    ALTER COLUMN delivery_address SET NOT NULL,
    ADD CONSTRAINT uq_shipments_number UNIQUE (shipment_number),
    ADD CONSTRAINT uq_shipments_waybill_number UNIQUE (waybill_number),
    ADD CONSTRAINT chk_shipments_number_not_blank CHECK (BTRIM(shipment_number) <> ''),
    ADD CONSTRAINT chk_shipments_delivery_address_not_blank CHECK (BTRIM(delivery_address) <> ''),
    ADD CONSTRAINT chk_shipments_waybill_not_blank CHECK (waybill_number IS NULL OR BTRIM(waybill_number) <> '');

ALTER TABLE shipment_items
    ALTER COLUMN shipment_id SET NOT NULL,
    ALTER COLUMN order_item_id SET NOT NULL,
    ALTER COLUMN product_id SET NOT NULL,
    ALTER COLUMN quantity SET NOT NULL,
    ADD CONSTRAINT chk_shipment_items_quantity CHECK (quantity > 0);

ALTER TABLE audit_log
    ALTER COLUMN action_type SET NOT NULL,
    ALTER COLUMN table_name SET NOT NULL,
    ALTER COLUMN changed_at SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN success SET DEFAULT TRUE,
    ADD CONSTRAINT chk_audit_log_action_type CHECK (action_type IN ('INSERT', 'UPDATE', 'DELETE', 'LOGIN', 'LOGOUT')),
    ADD CONSTRAINT chk_audit_log_table_name_not_blank CHECK (BTRIM(table_name) <> '');

ALTER TABLE users
    ADD CONSTRAINT fk_users_status_code
        FOREIGN KEY (status_code) REFERENCES user_statuses (status_code) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_users_customer_id
        FOREIGN KEY (customer_id) REFERENCES customers (customer_id) ON DELETE RESTRICT;

ALTER TABLE role_permissions
    ADD CONSTRAINT fk_role_permissions_role_id
        FOREIGN KEY (role_id) REFERENCES roles (role_id) ON DELETE RESTRICT;

ALTER TABLE user_roles
    ADD CONSTRAINT fk_user_roles_user_id
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_user_roles_role_id
        FOREIGN KEY (role_id) REFERENCES roles (role_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_user_roles_assigned_by_user_id
        FOREIGN KEY (assigned_by_user_id) REFERENCES users (user_id) ON DELETE RESTRICT;

ALTER TABLE supplier_materials
    ADD CONSTRAINT fk_supplier_materials_supplier_id
        FOREIGN KEY (supplier_id) REFERENCES suppliers (supplier_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_supplier_materials_material_id
        FOREIGN KEY (material_id) REFERENCES raw_materials (material_id) ON DELETE RESTRICT;

ALTER TABLE raw_material_deliveries
    ADD CONSTRAINT fk_raw_material_deliveries_supplier_id
        FOREIGN KEY (supplier_id) REFERENCES suppliers (supplier_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_raw_material_deliveries_status_code
        FOREIGN KEY (status_code) REFERENCES delivery_statuses (status_code) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_raw_material_deliveries_received_by_user_id
        FOREIGN KEY (received_by_user_id) REFERENCES users (user_id) ON DELETE RESTRICT;

ALTER TABLE delivery_items
    ADD CONSTRAINT fk_delivery_items_delivery_id
        FOREIGN KEY (delivery_id) REFERENCES raw_material_deliveries (delivery_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_delivery_items_material_id
        FOREIGN KEY (material_id) REFERENCES raw_materials (material_id) ON DELETE RESTRICT;

ALTER TABLE raw_material_stock
    ADD CONSTRAINT fk_raw_material_stock_material_id
        FOREIGN KEY (material_id) REFERENCES raw_materials (material_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_raw_material_stock_delivery_item_material
        FOREIGN KEY (delivery_item_id, material_id) REFERENCES delivery_items (delivery_item_id, material_id) ON DELETE RESTRICT;

ALTER TABLE tech_cards
    ADD CONSTRAINT fk_tech_cards_product_id
        FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_tech_cards_status_code
        FOREIGN KEY (status_code) REFERENCES tech_card_statuses (status_code) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_tech_cards_approved_by_user_id
        FOREIGN KEY (approved_by_user_id) REFERENCES users (user_id) ON DELETE RESTRICT;

ALTER TABLE recipe_items
    ADD CONSTRAINT fk_recipe_items_tech_card_id
        FOREIGN KEY (tech_card_id) REFERENCES tech_cards (tech_card_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_recipe_items_material_id
        FOREIGN KEY (material_id) REFERENCES raw_materials (material_id) ON DELETE RESTRICT;

ALTER TABLE customer_orders
    ADD CONSTRAINT fk_customer_orders_customer_id
        FOREIGN KEY (customer_id) REFERENCES customers (customer_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_customer_orders_status_code
        FOREIGN KEY (status_code) REFERENCES order_statuses (status_code) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_customer_orders_created_by_user_id
        FOREIGN KEY (created_by_user_id) REFERENCES users (user_id) ON DELETE RESTRICT;

ALTER TABLE order_items
    ADD CONSTRAINT fk_order_items_order_id
        FOREIGN KEY (order_id) REFERENCES customer_orders (order_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_order_items_product_id
        FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE RESTRICT;

ALTER TABLE production_batches
    ADD CONSTRAINT fk_production_batches_tech_card_product
        FOREIGN KEY (tech_card_id, product_id) REFERENCES tech_cards (tech_card_id, product_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_production_batches_responsible_user_id
        FOREIGN KEY (responsible_user_id) REFERENCES users (user_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_production_batches_status_code
        FOREIGN KEY (status_code) REFERENCES production_statuses (status_code) ON DELETE RESTRICT;

ALTER TABLE finished_goods_stock
    ADD CONSTRAINT fk_finished_goods_stock_product_id
        FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_finished_goods_stock_production_batch_product
        FOREIGN KEY (production_batch_id, product_id) REFERENCES production_batches (production_batch_id, product_id) ON DELETE RESTRICT;

ALTER TABLE quality_checks
    ADD CONSTRAINT fk_quality_checks_delivery_item_id
        FOREIGN KEY (delivery_item_id) REFERENCES delivery_items (delivery_item_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_quality_checks_production_batch_id
        FOREIGN KEY (production_batch_id) REFERENCES production_batches (production_batch_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_quality_checks_inspector_user_id
        FOREIGN KEY (inspector_user_id) REFERENCES users (user_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_quality_checks_result_code
        FOREIGN KEY (result_code) REFERENCES quality_statuses (status_code) ON DELETE RESTRICT;

ALTER TABLE invoices
    ADD CONSTRAINT fk_invoices_order_id
        FOREIGN KEY (order_id) REFERENCES customer_orders (order_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_invoices_status_code
        FOREIGN KEY (status_code) REFERENCES invoice_statuses (status_code) ON DELETE RESTRICT;

ALTER TABLE shipments
    ADD CONSTRAINT fk_shipments_order_id
        FOREIGN KEY (order_id) REFERENCES customer_orders (order_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_shipments_status_code
        FOREIGN KEY (status_code) REFERENCES shipment_statuses (status_code) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_shipments_created_by_user_id
        FOREIGN KEY (created_by_user_id) REFERENCES users (user_id) ON DELETE RESTRICT;

ALTER TABLE shipment_items
    ADD CONSTRAINT fk_shipment_items_shipment_id
        FOREIGN KEY (shipment_id) REFERENCES shipments (shipment_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_shipment_items_order_item_product
        FOREIGN KEY (order_item_id, product_id) REFERENCES order_items (order_item_id, product_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_shipment_items_finished_stock_product
        FOREIGN KEY (finished_stock_id, product_id) REFERENCES finished_goods_stock (finished_stock_id, product_id) ON DELETE RESTRICT;

ALTER TABLE audit_log
    ADD CONSTRAINT fk_audit_log_user_id
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE RESTRICT;

CREATE OR REPLACE FUNCTION validate_delivery_item_expiry()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    delivery_dt DATE;
BEGIN
    SELECT d.delivery_date
    INTO delivery_dt
    FROM raw_material_deliveries AS d
    WHERE d.delivery_id = NEW.delivery_id;

    IF delivery_dt IS NULL THEN
        RAISE EXCEPTION 'Delivery % does not exist for delivery item validation.', NEW.delivery_id;
    END IF;

    IF NEW.expiry_date <= delivery_dt THEN
        RAISE EXCEPTION 'Expiry date (%) must be later than delivery date (%).', NEW.expiry_date, delivery_dt;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validate_delivery_item_expiry ON delivery_items;
CREATE TRIGGER trg_validate_delivery_item_expiry
BEFORE INSERT OR UPDATE ON delivery_items
FOR EACH ROW
EXECUTE FUNCTION validate_delivery_item_expiry();

CREATE OR REPLACE FUNCTION validate_shipment_dates()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    order_ts TIMESTAMP WITH TIME ZONE;
BEGIN
    IF NEW.shipped_at IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT o.order_date
    INTO order_ts
    FROM customer_orders AS o
    WHERE o.order_id = NEW.order_id;

    IF order_ts IS NULL THEN
        RAISE EXCEPTION 'Order % does not exist for shipment validation.', NEW.order_id;
    END IF;

    IF NEW.shipped_at < order_ts THEN
        RAISE EXCEPTION 'Shipment date (%) cannot be earlier than order date (%).', NEW.shipped_at, order_ts;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validate_shipment_dates ON shipments;
CREATE TRIGGER trg_validate_shipment_dates
BEFORE INSERT OR UPDATE ON shipments
FOR EACH ROW
EXECUTE FUNCTION validate_shipment_dates();
