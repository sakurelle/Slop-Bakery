# Инструкция по запуску

## Запуск через Docker Compose

1. Скопировать `configuration/.env.example` в `configuration/.env`.
2. При необходимости изменить параметры подключения, `APP_SECRET_KEY`, `WEB_PORT` и `POSTGRES_PORT`.
3. Запустить сервисы:

```bash
docker compose --env-file configuration/.env -f configuration/docker-compose.yml up --build
```

После запуска:

- БД PostgreSQL работает как сервис `db`;
- веб-интерфейс доступен на `http://localhost:8000`;
- веб-контейнер подключается к базе по адресу `db:5432`.

## Запуск на Windows

1. Установить Docker Desktop.
2. Открыть PowerShell в корне проекта.
3. При необходимости разрешить выполнение локальных скриптов:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

4. Создать `configuration/.env`.
5. Если порт `5432` на хосте занят, изменить внешний порт, например:

```env
POSTGRES_PORT=15432
```

Это влияет только на публикацию порта на хосте. Внутри Docker PostgreSQL продолжает слушать `5432`.

## Пересоздание базы данных

Используйте один из скриптов:

```bash
./scripts/reset_db.sh
```

или

```powershell
.\scripts\reset_db.ps1
```

Скрипты:

- поднимают сервис `db`;
- ждут готовности PostgreSQL через `pg_isready`;
- переходят в каталог `database/initialization`;
- выполняют `99_run_all.sql`.

Отдельный запуск `07_test_queries.sql` после этого не требуется, потому что он уже подключается из `99_run_all.sql`.

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
  sh -lc 'cd /workspace/database/checks && psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f 07_test_queries.sql'
```

Для веб-интерфейса см. `docs/launch/web_interface_guide.md`.
