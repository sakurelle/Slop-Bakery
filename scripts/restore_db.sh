#!/usr/bin/env bash
set -euo pipefail

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-bakery_security_db}"
DB_USER="${DB_USER:-bakery_admin_user}"
DB_PASSWORD="${DB_PASSWORD:-change_me}"
FORCE_RESTORE="${FORCE_RESTORE:-0}"

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 path/to/backup.sql" >&2
    exit 1
fi

backup_file="$1"

if [[ ! -f "$backup_file" ]]; then
    echo "Backup file not found: $backup_file" >&2
    exit 1
fi

echo "Warning: restore will change database '$DB_NAME' on $DB_HOST:$DB_PORT."

if [[ "$FORCE_RESTORE" != "1" ]]; then
    read -r -p "Type YES to continue: " confirmation
    if [[ "$confirmation" != "YES" ]]; then
        echo "Restore cancelled."
        exit 1
    fi
fi

if PGPASSWORD="$DB_PASSWORD" psql \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --dbname="$DB_NAME" \
    --file="$backup_file"; then
    echo "Restore completed successfully from: $backup_file"
else
    echo "Restore failed from: $backup_file" >&2
    exit 1
fi
