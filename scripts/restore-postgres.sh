#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
	printf 'Usage: %s backups/postgres_YYYYMMDDTHHMMSSZ.sql.gz\n' "$0" >&2
	exit 2
fi

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
COMPOSE=${COMPOSE:-docker compose}
BACKUP_FILE=$1

cd "$ROOT_DIR"

gzip -dc "$BACKUP_FILE" | $COMPOSE exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
