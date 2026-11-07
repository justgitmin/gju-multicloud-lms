#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p backups
backup_file="backups/lms-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$backup_file"
gzip -t "$backup_file"
printf 'Backup created: %s\n' "$backup_file"
