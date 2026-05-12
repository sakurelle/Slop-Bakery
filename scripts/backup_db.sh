#!/usr/bin/env bash
set -euo pipefail

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-bakery_security_db}"
DB_USER="${DB_USER:-bakery_admin_user}"
DB_PASSWORD="${DB_PASSWORD:-change_me}"
BACKUP_DIR="${BACKUP_DIR:-backups}"

mkdir -p "$BACKUP_DIR"

timestamp="$(date +%Y%m%d_%H%M%S)"
backup_file="$BACKUP_DIR/bakery_${timestamp}.sql"

if PGPASSWORD="$DB_PASSWORD" pg_dump \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --dbname="$DB_NAME" \
    --format=plain \
    --file="$backup_file"; then
    echo "Backup created successfully: $backup_file"
else
    echo "Backup failed for database '$DB_NAME' on $DB_HOST:$DB_PORT." >&2
    exit 1
fi
