# Роли и права доступа

## Логические роли пользователей

### admin

- Полный административный доступ к прикладочным данным.
- Управление пользователями, ролями, справочниками, заказами, производством и аудитом.

### technologist

- Работа с продукцией, технологическими картами, рецептурами и производственными партиями.
- Просмотр справочников сырья, заказов и результатов контроля качества.

### warehouse_worker

- Работа с поставками сырья, складскими остатками и отгрузками готовой продукции.
- Просмотр заказов, продукции и производственных партий.

### quality_control

- Проведение и регистрация контроля качества сырья и готовой продукции.
- Просмотр технологических карт, партий производства и поставок.

### client

- Просмотр каталога продукции, заказов, счетов и отгрузок.
- Полных административных прав не получает.

## SQL-роли PostgreSQL

В базе создаются роли:

- `bakery_admin`
- `bakery_technologist`
- `bakery_warehouse`
- `bakery_quality`
- `bakery_client`

Эти роли предназначены для назначения реальным учётным записям PostgreSQL и отражают модель разграничения доступа на уровне СУБД.

## Права доступа по ролям

### bakery_admin

- `USAGE` на схему `public`
- `SELECT`, `INSERT`, `UPDATE`, `DELETE` на все таблицы

### bakery_technologist

- `SELECT` на справочники статусов, `users`, `roles`, `user_roles`, `raw_materials`, `products`, `tech_cards`, `recipe_items`, `customer_orders`, `order_items`, `production_batches`, `quality_checks`
- `INSERT`, `UPDATE` на `products`, `tech_cards`, `recipe_items`, `production_batches`

### bakery_warehouse

- `SELECT` на статусы, `customers`, `users`, `suppliers`, `raw_materials`, `products`, `customer_orders`, `order_items`, `production_batches`, `finished_goods_stock`
- `INSERT`, `UPDATE` на `suppliers`, `supplier_materials`, `raw_material_deliveries`, `delivery_items`, `raw_material_stock`, `finished_goods_stock`, `shipments`, `shipment_items`

### bakery_quality

- `SELECT` на статусы, `users`, `suppliers`, `raw_materials`, `raw_material_deliveries`, `delivery_items`, `products`, `tech_cards`, `production_batches`
- `INSERT`, `UPDATE` на `quality_checks`

### bakery_client

- `SELECT` на `products`, `customer_orders`, `order_items`, `invoices`, `shipments`, `shipment_items` и справочники статусов заказов, счетов и отгрузок

## Принципы защиты

- Права выданы по принципу минимально необходимых привилегий.
- Полный доступ есть только у `bakery_admin`.
- Роли не получают лишних прав на удаление данных.
- Для контроля изменений используется отдельный журнал `audit_log`.
