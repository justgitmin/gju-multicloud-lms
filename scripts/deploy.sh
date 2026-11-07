#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Explicit source revision: never silently pull and deploy a moving branch.
if [[ ! -f .env ]]; then echo 'Create .env from .env.example first.' >&2; exit 1; fi
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then echo 'Tracked files have local changes. Review them before deployment.' >&2; exit 1; fi
compose=(docker compose -f compose.yaml -f compose.prod.yaml)
"${compose[@]}" config --quiet
"${compose[@]}" up -d db
if "${compose[@]}" exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT to_regclass('\''public.\"User\"'\'') IS NOT NULL"' | tr -d ' \r\n' | grep -q '^t$'; then
 bash scripts/backup.sh
fi
"${compose[@]}" build web tools
"${compose[@]}" --profile tools run --rm tools npm run db:migrate
"${compose[@]}" up -d web caddy
curl --fail --retry 15 --retry-delay 2 --retry-connrefused --silent http://127.0.0.1:3000/api/health
printf '\nDEPLOYMENT_HEALTH_OK\n'
