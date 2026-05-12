-- Row-Level Security for customer data.
-- The web application writes the authenticated application user id to
-- app.current_user_id. Client policies resolve this user to users.customer_id
-- and allow reading only rows that belong to the same customer.

CREATE OR REPLACE FUNCTION app_current_customer_id()
RETURNS BIGINT
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT u.customer_id
    FROM users AS u
    WHERE u.user_id = NULLIF(current_setting('app.current_user_id', true), '')::BIGINT
$$;

REVOKE ALL ON FUNCTION app_current_customer_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_current_customer_id() TO
    bakery_admin,
    bakery_technologist,
    bakery_warehouse,
    bakery_quality,
    bakery_client;

ALTER TABLE customer_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE shipments ENABLE ROW LEVEL SECURITY;
ALTER TABLE shipment_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS customer_orders_staff_access ON customer_orders;
CREATE POLICY customer_orders_staff_access
ON customer_orders
FOR ALL
TO bakery_admin, bakery_technologist, bakery_warehouse, bakery_quality
USING (TRUE)
WITH CHECK (TRUE);

DROP POLICY IF EXISTS customer_orders_client_select_own ON customer_orders;
CREATE POLICY customer_orders_client_select_own
ON customer_orders
FOR SELECT
TO bakery_client
USING (customer_id = app_current_customer_id());

DROP POLICY IF EXISTS order_items_staff_access ON order_items;
CREATE POLICY order_items_staff_access
ON order_items
FOR ALL
TO bakery_admin, bakery_technologist, bakery_warehouse, bakery_quality
USING (TRUE)
WITH CHECK (TRUE);

DROP POLICY IF EXISTS order_items_client_select_own ON order_items;
CREATE POLICY order_items_client_select_own
ON order_items
FOR SELECT
TO bakery_client
USING (
    EXISTS (
        SELECT 1
        FROM customer_orders AS co
        WHERE co.order_id = order_items.order_id
          AND co.customer_id = app_current_customer_id()
    )
);

DROP POLICY IF EXISTS invoices_staff_access ON invoices;
CREATE POLICY invoices_staff_access
ON invoices
FOR ALL
TO bakery_admin
USING (TRUE)
WITH CHECK (TRUE);

DROP POLICY IF EXISTS invoices_client_select_own ON invoices;
CREATE POLICY invoices_client_select_own
ON invoices
FOR SELECT
TO bakery_client
USING (
    EXISTS (
        SELECT 1
        FROM customer_orders AS co
        WHERE co.order_id = invoices.order_id
          AND co.customer_id = app_current_customer_id()
    )
);

DROP POLICY IF EXISTS shipments_staff_access ON shipments;
CREATE POLICY shipments_staff_access
ON shipments
FOR ALL
TO bakery_admin, bakery_warehouse
USING (TRUE)
WITH CHECK (TRUE);

DROP POLICY IF EXISTS shipments_client_select_own ON shipments;
CREATE POLICY shipments_client_select_own
ON shipments
FOR SELECT
TO bakery_client
USING (
    EXISTS (
        SELECT 1
        FROM customer_orders AS co
        WHERE co.order_id = shipments.order_id
          AND co.customer_id = app_current_customer_id()
    )
);

DROP POLICY IF EXISTS shipment_items_staff_access ON shipment_items;
CREATE POLICY shipment_items_staff_access
ON shipment_items
FOR ALL
TO bakery_admin, bakery_warehouse
USING (TRUE)
WITH CHECK (TRUE);

DROP POLICY IF EXISTS shipment_items_client_select_own ON shipment_items;
CREATE POLICY shipment_items_client_select_own
ON shipment_items
FOR SELECT
TO bakery_client
USING (
    EXISTS (
        SELECT 1
        FROM shipments AS s
        JOIN customer_orders AS co ON co.order_id = s.order_id
        WHERE s.shipment_id = shipment_items.shipment_id
          AND co.customer_id = app_current_customer_id()
    )
);
