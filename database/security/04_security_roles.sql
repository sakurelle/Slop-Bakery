DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bakery_admin') THEN
        CREATE ROLE bakery_admin NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bakery_technologist') THEN
        CREATE ROLE bakery_technologist NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bakery_warehouse') THEN
        CREATE ROLE bakery_warehouse NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bakery_quality') THEN
        CREATE ROLE bakery_quality NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bakery_client') THEN
        CREATE ROLE bakery_client NOLOGIN;
    END IF;
END;
$$;

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;

GRANT USAGE ON SCHEMA public TO bakery_admin, bakery_technologist, bakery_warehouse, bakery_quality, bakery_client;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO bakery_admin;

GRANT SELECT ON
    order_statuses,
    invoice_statuses,
    shipment_statuses,
    delivery_statuses,
    production_statuses,
    quality_statuses,
    tech_card_statuses,
    user_statuses,
    users,
    roles,
    user_roles,
    raw_materials,
    products,
    tech_cards,
    recipe_items,
    customer_orders,
    order_items,
    production_batches,
    quality_checks
TO bakery_technologist;

GRANT INSERT, UPDATE ON
    products,
    tech_cards,
    recipe_items,
    production_batches
TO bakery_technologist;

GRANT SELECT ON
    order_statuses,
    shipment_statuses,
    delivery_statuses,
    production_statuses,
    user_statuses,
    customers,
    users,
    suppliers,
    raw_materials,
    products,
    customer_orders,
    order_items,
    production_batches,
    finished_goods_stock
TO bakery_warehouse;

GRANT INSERT, UPDATE ON
    suppliers,
    supplier_materials,
    raw_material_deliveries,
    delivery_items,
    raw_material_stock,
    finished_goods_stock,
    shipments,
    shipment_items
TO bakery_warehouse;

GRANT SELECT ON
    delivery_statuses,
    production_statuses,
    quality_statuses,
    tech_card_statuses,
    user_statuses,
    users,
    suppliers,
    raw_materials,
    raw_material_deliveries,
    delivery_items,
    products,
    tech_cards,
    production_batches
TO bakery_quality;

GRANT SELECT, INSERT, UPDATE ON quality_checks TO bakery_quality;

GRANT SELECT ON
    order_statuses,
    invoice_statuses,
    shipment_statuses,
    products,
    customer_orders,
    order_items,
    invoices,
    shipments,
    shipment_items
TO bakery_client;
