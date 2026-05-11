# Структура базы данных

## Справочники статусов

Все справочники статусов имеют одинаковую структуру:

- `status_code VARCHAR(32)` — первичный ключ.
- `name VARCHAR(100)` — уникальное наименование статуса.
- `description TEXT` — описание статуса.

Ограничения:

- `status_code` обязателен и не может быть пустым.
- `name` обязателен и не может быть пустым.

Справочники:

- `order_statuses`
- `invoice_statuses`
- `shipment_statuses`
- `delivery_statuses`
- `production_statuses`
- `quality_statuses`
- `tech_card_statuses`
- `user_statuses`

## Основные таблицы

### customers

- PK: `customer_id`
- Поля: `customer_type`, `full_name`, `company_name`, `phone`, `email`, `delivery_address`, `created_at`, `is_active`
- Ограничения: тип клиента `individual` или `company`; для `individual` обязательно `full_name`; для `company` обязательно `company_name`; `email` уникален при наличии

### suppliers

- PK: `supplier_id`
- Поля: `company_name`, `contact_person`, `phone`, `email`, `address`, `created_at`, `is_active`
- Ограничения: `company_name` уникален; `email` уникален при наличии

### raw_materials

- PK: `material_id`
- Поля: `name`, `unit`, `min_stock_qty`, `shelf_life_days`, `storage_conditions`, `is_active`
- Ограничения: `name` уникален; минимальный остаток неотрицателен; срок годности положителен при наличии

### supplier_materials

- PK: `supplier_material_id`
- FK: `supplier_id -> suppliers`, `material_id -> raw_materials`
- Поля: `purchase_price`, `lead_time_days`, `is_active`
- Ограничения: уникальная пара `supplier_id + material_id`

### raw_material_deliveries

- PK: `delivery_id`
- FK: `supplier_id -> suppliers`, `status_code -> delivery_statuses`, `received_by_user_id -> users`
- Поля: `delivery_number`, `delivery_date`, `document_ref`, `total_amount`, `note`
- Ограничения: `delivery_number` уникален; сумма неотрицательна

### delivery_items

- PK: `delivery_item_id`
- FK: `delivery_id -> raw_material_deliveries`, `material_id -> raw_materials`
- Поля: `quantity`, `unit_price`, `batch_number`, `expiry_date`
- Ограничения: количество больше нуля; цена неотрицательна; срок годности позже даты поставки; уникальность партии в пределах поставки

### raw_material_stock

- PK: `stock_id`
- FK: `material_id -> raw_materials`, `delivery_item_id -> delivery_items`
- Поля: `batch_number`, `quantity_current`, `expiry_date`, `updated_at`
- Ограничения: остаток неотрицателен; уникальность партии материала

### products

- PK: `product_id`
- Поля: `name`, `category`, `unit`, `price`, `shelf_life_days`, `is_active`, `created_at`
- Ограничения: `name` уникален; цена неотрицательна; срок годности положителен

### tech_cards

- PK: `tech_card_id`
- FK: `product_id -> products`, `status_code -> tech_card_statuses`, `approved_by_user_id -> users`
- Поля: `card_number`, `version`, `effective_from`, `effective_to`, `baking_time_min`, `baking_temperature_c`, `process_description`
- Ограничения: `card_number` уникален; `product_id + version` уникальны; только одна активная карта на продукт через частичный уникальный индекс

### recipe_items

- PK: `recipe_item_id`
- FK: `tech_card_id -> tech_cards`, `material_id -> raw_materials`
- Поля: `quantity`, `unit`, `stage`, `waste_percent`, `note`
- Ограничения: количество больше нуля; потери от `0` до `< 100`; уникальность материала и стадии в техкарте

### customer_orders

- PK: `order_id`
- FK: `customer_id -> customers`, `status_code -> order_statuses`, `created_by_user_id -> users`
- Поля: `order_number`, `order_date`, `planned_shipment_date`, `comment`
- Ограничения: `order_number` уникален; плановая дата отгрузки не раньше даты заказа

### order_items

- PK: `order_item_id`
- FK: `order_id -> customer_orders`, `product_id -> products`
- Поля: `quantity`, `unit_price`, `line_amount`
- Ограничения: количество больше нуля; цена неотрицательна; уникальность `order_id + product_id`

### production_batches

- PK: `production_batch_id`
- FK: `product_id + tech_card_id -> tech_cards`, `responsible_user_id -> users`, `status_code -> production_statuses`
- Поля: `batch_number`, `production_date`, `shift`, `quantity_produced`, `quantity_defective`, `note`
- Ограничения: `batch_number` уникален; дефект не превышает выпуск

### finished_goods_stock

- PK: `finished_stock_id`
- FK: `product_id -> products`, `production_batch_id + product_id -> production_batches`
- Поля: `batch_number`, `quantity_current`, `production_date`, `expiry_date`, `updated_at`
- Ограничения: остаток неотрицателен; срок годности позже даты производства

### quality_checks

- PK: `quality_check_id`
- FK: `delivery_item_id -> delivery_items`, `production_batch_id -> production_batches`, `inspector_user_id -> users`, `result_code -> quality_statuses`
- Поля: `check_type`, `checked_at`, `parameter_name`, `measured_value`, `standard_value`, `document_number`, `note`
- Ограничения: тип только `raw_material` или `finished_product`; заполняется либо `delivery_item_id`, либо `production_batch_id`

### invoices

- PK: `invoice_id`
- FK: `order_id -> customer_orders`, `status_code -> invoice_statuses`
- Поля: `invoice_number`, `issue_date`, `due_date`, `paid_at`, `amount`, `note`
- Ограничения: `invoice_number` уникален; дата оплаты не раньше даты выставления

### shipments

- PK: `shipment_id`
- FK: `order_id -> customer_orders`, `status_code -> shipment_statuses`, `created_by_user_id -> users`
- Поля: `shipment_number`, `shipped_at`, `delivery_address`, `waybill_number`, `note`
- Ограничения: `shipment_number` уникален; `waybill_number` уникален при наличии; дата отгрузки не раньше даты заказа

### shipment_items

- PK: `shipment_item_id`
- FK: `shipment_id -> shipments`, `order_item_id + product_id -> order_items`, `finished_stock_id + product_id -> finished_goods_stock`
- Поля: `quantity`
- Ограничения: количество больше нуля; продукция должна совпадать со строкой заказа и складским остатком готовой продукции

### users

- PK: `user_id`
- FK: `status_code -> user_statuses`, `customer_id -> customers`
- Поля: `username`, `password_hash`, `full_name`, `email`, `phone`, `created_at`, `last_login_at`
- Ограничения: `username` уникален; `email` уникален при наличии; хранится только хэш пароля

### roles

- PK: `role_id`
- Поля: `role_code`, `role_name`, `description`
- Ограничения: `role_code` и `role_name` уникальны

### user_roles

- PK: составной `user_id + role_id`
- FK: `user_id -> users`, `role_id -> roles`, `assigned_by_user_id -> users`
- Поля: `assigned_at`

### role_permissions

- PK: `permission_id`
- FK: `role_id -> roles`
- Поля: `object_name`, `can_select`, `can_insert`, `can_update`, `can_delete`
- Ограничения: уникальность `role_id + object_name`

### audit_log

- PK: `audit_id`
- FK: `user_id -> users`
- Поля: `action_type`, `table_name`, `record_id`, `changed_at`, `old_data`, `new_data`, `ip_address`, `success`
- Ограничения: `action_type` только `INSERT`, `UPDATE`, `DELETE`, `LOGIN`, `LOGOUT`

## Ключевые особенности модели

- продукция и технологические карты хранятся раздельно;
- заказ и строки заказа хранятся раздельно;
- поставка и строки поставки хранятся раздельно;
- отгрузка и строки отгрузки хранятся раздельно;
- состав рецептуры хранится построчно в `recipe_items`;
- связи многие-ко-многим реализованы только через промежуточные таблицы.
