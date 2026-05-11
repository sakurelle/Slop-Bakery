CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE order_statuses (
    status_code VARCHAR(32) PRIMARY KEY,
    name VARCHAR(100),
    description TEXT
);

CREATE TABLE invoice_statuses (
    status_code VARCHAR(32) PRIMARY KEY,
    name VARCHAR(100),
    description TEXT
);

CREATE TABLE shipment_statuses (
    status_code VARCHAR(32) PRIMARY KEY,
    name VARCHAR(100),
    description TEXT
);

CREATE TABLE delivery_statuses (
    status_code VARCHAR(32) PRIMARY KEY,
    name VARCHAR(100),
    description TEXT
);

CREATE TABLE production_statuses (
    status_code VARCHAR(32) PRIMARY KEY,
    name VARCHAR(100),
    description TEXT
);

CREATE TABLE quality_statuses (
    status_code VARCHAR(32) PRIMARY KEY,
    name VARCHAR(100),
    description TEXT
);

CREATE TABLE tech_card_statuses (
    status_code VARCHAR(32) PRIMARY KEY,
    name VARCHAR(100),
    description TEXT
);

CREATE TABLE user_statuses (
    status_code VARCHAR(32) PRIMARY KEY,
    name VARCHAR(100),
    description TEXT
);

CREATE TABLE customers (
    customer_id BIGINT PRIMARY KEY,
    customer_type VARCHAR(20),
    full_name VARCHAR(200),
    company_name VARCHAR(200),
    phone VARCHAR(32),
    email VARCHAR(255),
    delivery_address TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN
);

CREATE TABLE suppliers (
    supplier_id BIGINT PRIMARY KEY,
    company_name VARCHAR(200),
    contact_person VARCHAR(200),
    phone VARCHAR(32),
    email VARCHAR(255),
    address TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN
);

CREATE TABLE raw_materials (
    material_id BIGINT PRIMARY KEY,
    name VARCHAR(150),
    unit VARCHAR(20),
    min_stock_qty NUMERIC(12,3),
    shelf_life_days INTEGER,
    storage_conditions TEXT,
    is_active BOOLEAN
);

CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(100),
    password_hash TEXT,
    full_name VARCHAR(200),
    email VARCHAR(255),
    phone VARCHAR(32),
    status_code VARCHAR(32),
    customer_id BIGINT,
    created_at TIMESTAMP WITH TIME ZONE,
    last_login_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE roles (
    role_id BIGINT PRIMARY KEY,
    role_code VARCHAR(50),
    role_name VARCHAR(100),
    description TEXT
);

CREATE TABLE role_permissions (
    permission_id BIGINT PRIMARY KEY,
    role_id BIGINT,
    object_name VARCHAR(100),
    can_select BOOLEAN,
    can_insert BOOLEAN,
    can_update BOOLEAN,
    can_delete BOOLEAN
);

CREATE TABLE user_roles (
    user_id BIGINT,
    role_id BIGINT,
    assigned_at TIMESTAMP WITH TIME ZONE,
    assigned_by_user_id BIGINT,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE supplier_materials (
    supplier_material_id BIGINT PRIMARY KEY,
    supplier_id BIGINT,
    material_id BIGINT,
    purchase_price NUMERIC(12,2),
    lead_time_days INTEGER,
    is_active BOOLEAN
);

CREATE TABLE raw_material_deliveries (
    delivery_id BIGINT PRIMARY KEY,
    supplier_id BIGINT,
    delivery_number VARCHAR(50),
    delivery_date DATE,
    status_code VARCHAR(32),
    received_by_user_id BIGINT,
    document_ref VARCHAR(100),
    total_amount NUMERIC(12,2),
    note TEXT
);

CREATE TABLE delivery_items (
    delivery_item_id BIGINT PRIMARY KEY,
    delivery_id BIGINT,
    material_id BIGINT,
    quantity NUMERIC(12,3),
    unit_price NUMERIC(12,2),
    batch_number VARCHAR(80),
    expiry_date DATE
);

CREATE TABLE raw_material_stock (
    stock_id BIGINT PRIMARY KEY,
    material_id BIGINT,
    delivery_item_id BIGINT,
    batch_number VARCHAR(80),
    quantity_current NUMERIC(12,3),
    expiry_date DATE,
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE products (
    product_id BIGINT PRIMARY KEY,
    name VARCHAR(150),
    category VARCHAR(100),
    unit VARCHAR(20),
    price NUMERIC(12,2),
    shelf_life_days INTEGER,
    is_active BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE tech_cards (
    tech_card_id BIGINT PRIMARY KEY,
    product_id BIGINT,
    card_number VARCHAR(50),
    version INTEGER,
    status_code VARCHAR(32),
    effective_from DATE,
    effective_to DATE,
    baking_time_min INTEGER,
    baking_temperature_c NUMERIC(5,2),
    process_description TEXT,
    approved_by_user_id BIGINT
);

CREATE TABLE recipe_items (
    recipe_item_id BIGINT PRIMARY KEY,
    tech_card_id BIGINT,
    material_id BIGINT,
    quantity NUMERIC(12,3),
    unit VARCHAR(20),
    stage VARCHAR(100),
    waste_percent NUMERIC(5,2),
    note TEXT
);

CREATE TABLE customer_orders (
    order_id BIGINT PRIMARY KEY,
    order_number VARCHAR(50),
    customer_id BIGINT,
    order_date TIMESTAMP WITH TIME ZONE,
    planned_shipment_date DATE,
    status_code VARCHAR(32),
    created_by_user_id BIGINT,
    comment TEXT
);

CREATE TABLE order_items (
    order_item_id BIGINT PRIMARY KEY,
    order_id BIGINT,
    product_id BIGINT,
    quantity NUMERIC(12,3),
    unit_price NUMERIC(12,2),
    line_amount NUMERIC(12,2)
);

CREATE TABLE production_batches (
    production_batch_id BIGINT PRIMARY KEY,
    batch_number VARCHAR(80),
    product_id BIGINT,
    tech_card_id BIGINT,
    production_date TIMESTAMP WITH TIME ZONE,
    shift VARCHAR(20),
    quantity_produced NUMERIC(12,3),
    quantity_defective NUMERIC(12,3),
    responsible_user_id BIGINT,
    status_code VARCHAR(32),
    note TEXT
);

CREATE TABLE finished_goods_stock (
    finished_stock_id BIGINT PRIMARY KEY,
    product_id BIGINT,
    production_batch_id BIGINT,
    batch_number VARCHAR(80),
    quantity_current NUMERIC(12,3),
    production_date DATE,
    expiry_date DATE,
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE quality_checks (
    quality_check_id BIGINT PRIMARY KEY,
    check_type VARCHAR(30),
    delivery_item_id BIGINT,
    production_batch_id BIGINT,
    checked_at TIMESTAMP WITH TIME ZONE,
    inspector_user_id BIGINT,
    result_code VARCHAR(32),
    parameter_name VARCHAR(150),
    measured_value VARCHAR(100),
    standard_value VARCHAR(100),
    document_number VARCHAR(100),
    note TEXT
);

CREATE TABLE invoices (
    invoice_id BIGINT PRIMARY KEY,
    invoice_number VARCHAR(50),
    order_id BIGINT,
    issue_date DATE,
    due_date DATE,
    paid_at TIMESTAMP WITH TIME ZONE,
    amount NUMERIC(12,2),
    status_code VARCHAR(32),
    note TEXT
);

CREATE TABLE supplier_invoices (
    supplier_invoice_id BIGINT PRIMARY KEY,
    supplier_invoice_number VARCHAR(50),
    delivery_id BIGINT,
    supplier_id BIGINT,
    issue_date DATE,
    due_date DATE,
    paid_at TIMESTAMP WITH TIME ZONE,
    amount NUMERIC(12,2),
    status_code VARCHAR(32),
    document_ref VARCHAR(100),
    note TEXT
);

CREATE TABLE shipments (
    shipment_id BIGINT PRIMARY KEY,
    shipment_number VARCHAR(50),
    order_id BIGINT,
    shipped_at TIMESTAMP WITH TIME ZONE,
    status_code VARCHAR(32),
    delivery_address TEXT,
    waybill_number VARCHAR(100),
    created_by_user_id BIGINT,
    note TEXT
);

CREATE TABLE shipment_items (
    shipment_item_id BIGINT PRIMARY KEY,
    shipment_id BIGINT,
    order_item_id BIGINT,
    product_id BIGINT,
    finished_stock_id BIGINT,
    quantity NUMERIC(12,3)
);

CREATE TABLE audit_log (
    audit_id BIGINT PRIMARY KEY,
    user_id BIGINT,
    action_type VARCHAR(20),
    table_name VARCHAR(100),
    record_id VARCHAR(100),
    changed_at TIMESTAMP WITH TIME ZONE,
    old_data JSONB,
    new_data JSONB,
    ip_address INET,
    success BOOLEAN
);
