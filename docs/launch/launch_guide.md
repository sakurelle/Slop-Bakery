# Инструкция по запуску

## Запуск через Docker Compose

1. Скопировать `configuration/.env.example` в `configuration/.env`.
2. При необходимости изменить параметры подключения и `APP_SECRET_KEY`.
3. Запустить сервисы:

```bash
docker compose --env-file configuration/.env -f configuration/docker-compose.yml up --build
```

После запуска:

- БД PostgreSQL работает как сервис `db`;
- веб-интерфейс доступен на `http://localhost:8000`.

## Пересоздание базы данных

Используйте один из скриптов:

```bash
./scripts/reset_db.sh
```

или

```powershell
.\scripts\reset_db.ps1
```

Скрипты поднимают `db`, выполняют `database/initialization/99_run_all.sql` и затем запускают проверочные SQL-запросы.

## Запуск только веб-интерфейса

```bash
./scripts/start_web.sh
```

или

```powershell
.\scripts\start_web.ps1
```

## Порядок выполнения SQL-файлов

Последовательность:

1. `00_drop.sql`
2. `01_schema.sql`
3. `02_constraints.sql`
4. `03_indexes.sql`
5. `04_security_roles.sql`
6. `05_audit.sql`
7. `06_seed.sql`
8. `07_test_queries.sql`

Файл `99_run_all.sql` уже содержит правильный порядок подключения скриптов.

## Запуск проверочных запросов вручную

После инициализации можно отдельно выполнить:

```bash
docker compose --env-file configuration/.env -f configuration/docker-compose.yml exec -T db \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /workspace/database/checks/07_test_queries.sql
```

Для веб-интерфейса см. `docs/launch/web_interface_guide.md`.
