#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BACKUP_DIR=${BACKUP_DIR:-"$ROOT_DIR/backups"}
COMPOSE=${COMPOSE:-docker compose}
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
OUT_FILE="$BACKUP_DIR/postgres_$TIMESTAMP.sql.gz"

mkdir -p "$BACKUP_DIR"
cd "$ROOT_DIR"

$COMPOSE exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gzip > "$OUT_FILE"
chmod 600 "$OUT_FILE"

printf '%s\n' "$OUT_FILE"
