#!/usr/bin/env bash
# Restore compressed SQL dump into imperecta database.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ENV_LOCAL="${ROOT_DIR}/backend/.env.local"
ROOT_ENV_LOCAL="${ROOT_DIR}/.env.local"

if [[ -t 1 ]] && command -v tput >/dev/null 2>&1; then
  R="$(tput setaf 1)"; G="$(tput setaf 2)"; Y="$(tput setaf 3)"; B="$(tput bold)"; N="$(tput sgr0)"
else
  R=$'\033[0;31m'; G=$'\033[0;32m'; Y=$'\033[1;33m'; B=$'\033[1m'; N=$'\033[0m'
fi

ok() { echo "${G}${B}✅${N} $*"; }
warn() { echo "${Y}${B}⏳${N} $*"; }
err() { echo "${R}${B}❌${N} $*" >&2; }
info() { echo "${B}▶${N} $*"; }

run_compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    return 127
  fi
}

if [[ $# -ne 1 ]]; then
  err "Usage: ./db-import.sh <path-to-dump.sql.gz>"
  exit 1
fi

DUMP_FILE="$1"
if [[ ! -f "${DUMP_FILE}" ]]; then
  err "Dump file not found: ${DUMP_FILE}"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  err "docker is not installed."
  exit 1
fi
if ! run_compose version >/dev/null 2>&1; then
  err "docker compose / docker-compose is not available."
  exit 1
fi

if [[ -f "${BACKEND_ENV_LOCAL}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${BACKEND_ENV_LOCAL}"
  set +a
  ok "Loaded ${BACKEND_ENV_LOCAL}"
elif [[ -f "${ROOT_ENV_LOCAL}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ROOT_ENV_LOCAL}"
  set +a
  ok "Loaded ${ROOT_ENV_LOCAL}"
else
  warn "No .env.local found; using defaults."
fi

DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-imperecta_dev}"

if [[ -n "${DATABASE_URL:-}" ]]; then
  parsed_db="$(python3 - <<'PY'
import os
from urllib.parse import urlparse
u = os.getenv("DATABASE_URL", "")
if u:
    p = urlparse(u)
    user = p.username or ""
    db = (p.path or "/").lstrip("/")
    print(user)
    print(db)
PY
)"
  parsed_user="$(printf %s "${parsed_db}" | sed -n '1p')"
  parsed_name="$(printf %s "${parsed_db}" | sed -n '2p')"
  if [[ -n "${parsed_user}" ]]; then DB_USER="${parsed_user}"; fi
  if [[ -n "${parsed_name}" ]]; then DB_NAME="${parsed_name}"; fi
fi

warn "This will DROP and recreate schema public in ${DB_NAME}."
info "Restoring from: ${DUMP_FILE}"

run_compose exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U "${DB_USER}" -d "${DB_NAME}" \
  -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"

gzip -dc "${DUMP_FILE}" | run_compose exec -T postgres \
  pg_restore --clean --if-exists --no-owner --no-privileges -U "${DB_USER}" -d "${DB_NAME}"

ok "Import completed successfully into ${DB_NAME}."
