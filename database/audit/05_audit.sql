CREATE OR REPLACE FUNCTION audit_row_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    actor_user_id BIGINT;
    actor_ip INET;
    row_payload JSONB;
    old_payload JSONB;
    new_payload JSONB;
    record_id_parts TEXT[] := ARRAY[]::TEXT[];
    key_name TEXT;
    key_value TEXT;
    next_audit_id BIGINT;
    idx INTEGER;
BEGIN
    actor_user_id := NULLIF(current_setting('app.current_user_id', true), '')::BIGINT;
    actor_ip := NULLIF(current_setting('app.current_user_ip', true), '')::INET;

    IF TG_OP = 'DELETE' THEN
        old_payload := to_jsonb(OLD);
        row_payload := old_payload;
    ELSIF TG_OP = 'UPDATE' THEN
        old_payload := to_jsonb(OLD);
        new_payload := to_jsonb(NEW);
        row_payload := new_payload;
    ELSE
        new_payload := to_jsonb(NEW);
        row_payload := new_payload;
    END IF;

    IF TG_NARGS > 0 THEN
        FOR idx IN 0..TG_NARGS - 1 LOOP
            key_name := TG_ARGV[idx];
            key_value := COALESCE(row_payload ->> key_name, 'null');
            record_id_parts := array_append(record_id_parts, key_name || '=' || key_value);
        END LOOP;
    END IF;

    SELECT COALESCE(MAX(audit_id) + 1, 1)
    INTO next_audit_id
    FROM audit_log;

    INSERT INTO audit_log (
        audit_id,
        user_id,
        action_type,
        table_name,
        record_id,
        changed_at,
        old_data,
        new_data,
        ip_address,
        success
    )
    VALUES (
        next_audit_id,
        actor_user_id,
        TG_OP,
        TG_TABLE_NAME,
        NULLIF(array_to_string(record_id_parts, ', '), ''),
        CURRENT_TIMESTAMP,
        old_payload,
        new_payload,
        actor_ip,
        TRUE
    );

    RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE OR REPLACE FUNCTION log_auth_event(
    p_user_id BIGINT,
    p_action_type VARCHAR,
    p_ip_address INET DEFAULT NULL,
    p_success BOOLEAN DEFAULT TRUE
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    next_audit_id BIGINT;
BEGIN
    IF p_action_type NOT IN ('LOGIN', 'LOGOUT') THEN
        RAISE EXCEPTION 'Unsupported auth audit action type: %', p_action_type;
    END IF;

    SELECT COALESCE(MAX(audit_id) + 1, 1)
    INTO next_audit_id
    FROM audit_log;

    INSERT INTO audit_log (
        audit_id,
        user_id,
        action_type,
        table_name,
        record_id,
        changed_at,
        old_data,
        new_data,
        ip_address,
        success
    )
    VALUES (
        next_audit_id,
        p_user_id,
        p_action_type,
        'users',
        CASE WHEN p_user_id IS NULL THEN NULL ELSE 'user_id=' || p_user_id::TEXT END,
        CURRENT_TIMESTAMP,
        NULL,
        NULL,
        p_ip_address,
        p_success
    );
END;
$$;

DROP TRIGGER IF EXISTS trg_audit_customers ON customers;
CREATE TRIGGER trg_audit_customers
AFTER INSERT OR UPDATE OR DELETE ON customers
FOR EACH ROW
EXECUTE FUNCTION audit_row_change('customer_id');

DROP TRIGGER IF EXISTS trg_audit_suppliers ON suppliers;
CREATE TRIGGER trg_audit_suppliers
AFTER INSERT OR UPDATE OR DELETE ON suppliers
FOR EACH ROW
EXECUTE FUNCTION audit_row_change('supplier_id');

DROP TRIGGER IF EXISTS trg_audit_raw_materials ON raw_materials;
CREATE TRIGGER trg_audit_raw_materials
AFTER INSERT OR UPDATE OR DELETE ON raw_materials
FOR EACH ROW
EXECUTE FUNCTION audit_row_change('material_id');

DROP TRIGGER IF EXISTS trg_audit_products ON products;
CREATE TRIGGER trg_audit_products
AFTER INSERT OR UPDATE OR DELETE ON products
FOR EACH ROW
EXECUTE FUNCTION audit_row_change('product_id');

DROP TRIGGER IF EXISTS trg_audit_tech_cards ON tech_cards;
CREATE TRIGGER trg_audit_tech_cards
AFTER INSERT OR UPDATE OR DELETE ON tech_cards
FOR EACH ROW
EXECUTE FUNCTION audit_row_change('tech_card_id');

DROP TRIGGER IF EXISTS trg_audit_recipe_items ON recipe_items;
CREATE TRIGGER trg_audit_recipe_items
AFTER INSERT OR UPDATE OR DELETE ON recipe_items
FOR EACH ROW
EXECUTE FUNCTION audit_row_change('recipe_item_id');

DROP TRIGGER IF EXISTS trg_audit_customer_orders ON customer_orders;
CREATE TRIGGER trg_audit_customer_orders
AFTER INSERT OR UPDATE OR DELETE ON customer_orders
FOR EACH ROW
EXECUTE FUNCTION audit_row_change('order_id');

DROP TRIGGER IF EXISTS trg_audit_order_items ON order_items;
CREATE TRIGGER trg_audit_order_items
AFTER INSERT OR UPDATE OR DELETE ON order_items
FOR EACH ROW
EXECUTE FUNCTION audit_row_change('order_item_id');

DROP TRIGGER IF EXISTS trg_audit_production_batches ON production_batches;
CREATE TRIGGER trg_audit_production_batches
AFTER INSERT OR UPDATE OR DELETE ON production_batches
FOR EACH ROW
EXECUTE FUNCTION audit_row_change('production_batch_id');

DROP TRIGGER IF EXISTS trg_audit_quality_checks ON quality_checks;
CREATE TRIGGER trg_audit_quality_checks
AFTER INSERT OR UPDATE OR DELETE ON quality_checks
FOR EACH ROW
EXECUTE FUNCTION audit_row_change('quality_check_id');

DROP TRIGGER IF EXISTS trg_audit_invoices ON invoices;
CREATE TRIGGER trg_audit_invoices
AFTER INSERT OR UPDATE OR DELETE ON invoices
FOR EACH ROW
EXECUTE FUNCTION audit_row_change('invoice_id');

DROP TRIGGER IF EXISTS trg_audit_supplier_invoices ON supplier_invoices;
CREATE TRIGGER trg_audit_supplier_invoices
AFTER INSERT OR UPDATE OR DELETE ON supplier_invoices
FOR EACH ROW
EXECUTE FUNCTION audit_row_change('supplier_invoice_id');

DROP TRIGGER IF EXISTS trg_audit_shipments ON shipments;
CREATE TRIGGER trg_audit_shipments
AFTER INSERT OR UPDATE OR DELETE ON shipments
FOR EACH ROW
EXECUTE FUNCTION audit_row_change('shipment_id');

DROP TRIGGER IF EXISTS trg_audit_users ON users;
CREATE TRIGGER trg_audit_users
AFTER INSERT OR UPDATE OR DELETE ON users
FOR EACH ROW
EXECUTE FUNCTION audit_row_change('user_id');

DROP TRIGGER IF EXISTS trg_audit_roles ON roles;
CREATE TRIGGER trg_audit_roles
AFTER INSERT OR UPDATE OR DELETE ON roles
FOR EACH ROW
EXECUTE FUNCTION audit_row_change('role_id');

DROP TRIGGER IF EXISTS trg_audit_user_roles ON user_roles;
CREATE TRIGGER trg_audit_user_roles
AFTER INSERT OR UPDATE OR DELETE ON user_roles
FOR EACH ROW
EXECUTE FUNCTION audit_row_change('user_id', 'role_id');
