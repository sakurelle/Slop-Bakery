# Bakery DB Security Coursework

Репозиторий содержит учебный проект по дисциплине «Безопасность систем баз данных» для предметной области хлебозавода. В проект входят PostgreSQL-база данных, SQL-скрипты и локальный веб-интерфейс на FastAPI для демонстрации работы БД через браузер.

## Используемые технологии

- PostgreSQL
- Python
- FastAPI
- Jinja2
- psycopg
- Docker / Docker Compose

## Структура проекта

- `configuration/` — Docker Compose и пример переменных окружения.
- `database/initialization/` — удаление объектов, создание схемы, ограничений и индексов.
- `database/security/` — SQL-роли PostgreSQL и GRANT-права.
- `database/audit/` — функции и триггеры аудита.
- `database/seed/` — тестовые данные.
- `database/checks/` — проверочные SQL-запросы.
- `web/` — веб-приложение FastAPI, шаблоны Jinja2, CSS и Dockerfile.
- `docs/` — документация по структуре БД, ролям, аудиту и запуску.
- `scripts/` — скрипты пересоздания БД и запуска веб-интерфейса.

## Состав БД

Справочники статусов:

- `order_statuses`
- `invoice_statuses`
- `shipment_statuses`
- `delivery_statuses`
- `production_statuses`
- `quality_statuses`
- `tech_card_statuses`
- `user_statuses`

Основные таблицы:

- `customers`
- `suppliers`
- `raw_materials`
- `supplier_materials`
- `raw_material_deliveries`
- `delivery_items`
- `raw_material_stock`
- `products`
- `tech_cards`
- `recipe_items`
- `customer_orders`
- `order_items`
- `production_batches`
- `finished_goods_stock`
- `quality_checks`
- `invoices`
- `shipments`
- `shipment_items`
- `users`
- `roles`
- `user_roles`
- `role_permissions`
- `audit_log`

## Основные связи

- `customers` 1:M `customer_orders`
- `customer_orders` 1:M `order_items`, `invoices`, `shipments`
- `products` 1:M `order_items`, `tech_cards`, `production_batches`
- `tech_cards` 1:M `recipe_items`, `production_batches`
- `raw_materials` 1:M `recipe_items`, `delivery_items`, `raw_material_stock`
- `suppliers` 1:M `raw_material_deliveries`
- `raw_material_deliveries` 1:M `delivery_items`
- `production_batches` 1:M `finished_goods_stock`, `quality_checks`
- `shipments` 1:M `shipment_items`
- `users` M:N `roles` через `user_roles`
- `suppliers` M:N `raw_materials` через `supplier_materials`
- `customer_orders` M:N `products` через `order_items`
- `tech_cards` M:N `raw_materials` через `recipe_items`

## Ограничения целостности

Реализованы:

- первичные и внешние ключи;
- `UNIQUE`, `CHECK`, `DEFAULT`, `NOT NULL`;
- контроль неотрицательных количеств и цен;
- контроль корректности дат поставки, оплаты, отгрузки и срока годности;
- контроль обязательных полей для физлиц и компаний;
- запрет удаления связанных сущностей через `ON DELETE RESTRICT`;
- раздельное хранение заказов и их состава, поставок и их состава, продукции и технологических карт;
- частичный уникальный индекс для одной активной технологической карты на продукцию.

## Защита БД

В проекте реализованы:

- таблицы `users`, `roles`, `user_roles`, `role_permissions`;
- хранение только `password_hash`;
- аудит `INSERT`, `UPDATE`, `DELETE`, `LOGIN`, `LOGOUT` через `audit_log`;
- журналирование старых и новых значений в `JSONB`;
- SQL-роли PostgreSQL `bakery_admin`, `bakery_technologist`, `bakery_warehouse`, `bakery_quality`, `bakery_client`;
- разграничение доступа через `GRANT`;
- установка контекста пользователя из веб-интерфейса в `app.current_user_id` и `app.current_user_ip` для БД-аудита.

## Веб-интерфейс

Локальный веб-интерфейс доступен по адресу:

- `http://localhost:8000`

Возможности интерфейса:

- вход по пользователю из таблицы `users`;
- dashboard со сводной статистикой;
- просмотр и редактирование клиентов, поставщиков, сырья и продукции;
- просмотр и редактирование технологических карт и рецептур;
- создание заказов и позиций заказа;
- журнал производства и остатки готовой продукции;
- журнал контроля качества;
- создание счетов и отгрузок;
- отчёты по остаткам, продажам, производству и качеству;
- просмотр журнала аудита для администратора.

## Тестовые логины и пароли

После выполнения `database/seed/06_seed.sql` доступны пользователи:

- `admin / admin123`
- `technologist / tech123`
- `warehouse / warehouse123`
- `quality / quality123`
- `client / client123`

Пароли в БД сохраняются как bcrypt-хэши через `pgcrypto`.

## Порядок запуска SQL-файлов

Файлы выполняются в следующем порядке:

1. `database/initialization/00_drop.sql`
2. `database/initialization/01_schema.sql`
3. `database/initialization/02_constraints.sql`
4. `database/initialization/03_indexes.sql`
5. `database/security/04_security_roles.sql`
6. `database/audit/05_audit.sql`
7. `database/seed/06_seed.sql`
8. `database/checks/07_test_queries.sql`

Для удобства есть общий сценарий `database/initialization/99_run_all.sql`. Он подключает остальные SQL-файлы относительными путями, поэтому скрипты пересоздания БД запускают его из каталога `database/initialization`.

## Запуск через Docker

1. Скопировать `configuration/.env.example` в `configuration/.env`.
2. При необходимости изменить значения подключения, `APP_SECRET_KEY`, `WEB_PORT` и внешний порт PostgreSQL `POSTGRES_PORT`.
   Для реального или учебного демонстрационного запуска вне локального шаблона замените `APP_SECRET_KEY` на случайную строку и не оставляйте значение `change_me_session_key`.
3. Поднять сервисы:

```bash
docker compose --env-file configuration/.env -f configuration/docker-compose.yml up --build
```

После запуска:

- PostgreSQL доступен в Docker как сервис `db`;
- веб-интерфейс доступен на `http://localhost:8000`;
- веб-контейнер подключается к БД по адресу `db:5432`;
- внешний порт БД на хосте берётся из `POSTGRES_PORT`.

## Windows Launch

Для локального запуска на Windows:

1. Установить Docker Desktop.
2. Открыть PowerShell в корне проекта.
3. При необходимости разрешить выполнение скриптов на текущую сессию:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

4. Создать `configuration/.env` на основе `configuration/.env.example`.
5. Если порт `5432` занят, указать в `configuration/.env`, например:

```env
POSTGRES_PORT=15432
```

Это изменит только внешний порт на Windows-хосте. Внутри Docker база всё равно работает на `5432`, а веб-приложение подключается к `db:5432`.

6. Запустить проект:

```powershell
docker compose --env-file configuration/.env -f configuration/docker-compose.yml up --build
```

или

```powershell
.\scripts\start_web.ps1
```

## Пересоздание БД

Для пересоздания БД и повторной загрузки SQL-файлов:

```bash
./scripts/reset_db.sh
```

или

```powershell
.\scripts\reset_db.ps1
```

Скрипты:

- поднимают контейнер `db`;
- ждут готовности PostgreSQL;
- запускают `99_run_all.sql` из каталога `database/initialization`.

## Тестовые данные

В проекте подготовлены:

- 3 клиента;
- 3 поставщика;
- 6 видов сырья;
- 3 вида продукции;
- активные технологические карты и составы рецептур;
- поставки сырья и складские остатки;
- 3 заказа, счета и отгрузки;
- производственные партии и остатки готовой продукции;
- записи контроля качества;
- пользователи, роли и связи пользователей с ролями;
- записи аудита, созданные триггерами и функцией логирования входа/выхода.

Операционные даты в seed-данных заданы относительно `CURRENT_DATE` и `CURRENT_TIMESTAMP`, чтобы демо-остатки и сроки годности оставались актуальными при повторных запусках.

## Дополнительная документация

- `docs/launch/launch_guide.md` — общий порядок запуска проекта.
- `docs/launch/web_interface_guide.md` — работа с веб-интерфейсом.
- `docs/database-structure/database_structure.md` — структура таблиц.
- `docs/access-control/roles_and_permissions.md` — логические и SQL-роли.
- `docs/audit/audit_description.md` — описание аудита.

## Row-Level Security

Клиентские данные дополнительно защищены на уровне PostgreSQL через `database/security/06_row_level_security.sql`. Политики RLS включены для `customer_orders`, `order_items`, `invoices`, `shipments` и `shipment_items` и используют session variable `app.current_user_id`, которую приложение устанавливает в `web/app/database.py`. Клиент видит только записи, связанные с его `users.customer_id`, а роли администратора, технолога, склада и контроля качества сохраняют необходимые права.

Файл RLS подключен в общий сценарий `database/initialization/99_run_all.sql` после seed-данных и до проверочных запросов.

## Резервное копирование

Для логического резервного копирования PostgreSQL добавлен скрипт:

```bash
./scripts/backup_db.sh
```

Скрипт использует `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, создает каталог `backups` и сохраняет дамп с именем `bakery_YYYYMMDD_HHMMSS.sql`. Подробная стратегия описана в `docs/security/backup_strategy.md`.

## Восстановление БД

Для восстановления SQL-дампа используется:

```bash
FORCE_RESTORE=1 ./scripts/restore_db.sh backups/<file>.sql
```

Без `FORCE_RESTORE=1` скрипт запрашивает подтверждение, потому что восстановление изменяет состояние БД.

## Модель угроз

Модель угроз программной части находится в `docs/security/threat_model.md`. В ней перечислены угрозы несанкционированного доступа, SQL-инъекций, превышения полномочий, просмотра чужих заказов клиентом, сбоев БД, утечки резервных копий и меры, реально реализованные в проекте.

## Проверочные SQL-запросы

Файл `database/checks/07_test_queries.sql` содержит формальные разделы запросов для демонстрации: безопасный ввод данных, выборку с сортировкой, `DISTINCT`, константы и выражения, `GROUP BY`/`ORDER BY`, агрегатные функции, функции даты, строковые функции, предметные проверки и запросы по безопасности и аудиту.
