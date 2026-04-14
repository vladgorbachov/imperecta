#!/usr/bin/env bash
# Imperecta — full local dev startup (Postgres + Redis in Docker, backend native).
# Kali Linux / WSL (Windows 11) compatible.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
VENV_PY="${BACKEND_DIR}/.venv/bin/python"
VENV_PIP="${BACKEND_DIR}/.venv/bin/pip"
ENV_LOCAL="${BACKEND_DIR}/.env.local"

# Colors (ANSI); disable if not a TTY
if [[ -t 1 ]] && command -v tput >/dev/null 2>&1; then
  _R="$(tput setaf 1)"
  _G="$(tput setaf 2)"
  _Y="$(tput setaf 3)"
  _B="$(tput bold)"
  _N="$(tput sgr0)"
else
  _R=$'\033[0;31m'
  _G=$'\033[0;32m'
  _Y=$'\033[1;33m'
  _B=$'\033[1m'
  _N=$'\033[0m'
fi

ok()   { echo "${_G}${_B}✅${_N} $*"; }
warn() { echo "${_Y}${_B}⏳${_N} $*"; }
err()  { echo "${_R}${_B}❌${_N} $*" >&2; }
info() { echo "${_B}▶${_N} $*"; }

compose_desc() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
  else
    echo ""
  fi
}

run_compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    return 127
  fi
}

COMPOSE_LABEL="$(compose_desc)"
if [[ -z "${COMPOSE_LABEL}" ]]; then
  err "Neither 'docker compose' (v2 plugin) nor 'docker-compose' was found."
  err "Install Docker Desktop / Docker Engine + Compose, then retry."
  exit 1
fi

info "Using: ${COMPOSE_LABEL}"

if ! docker info >/dev/null 2>&1; then
  err "Docker daemon is not running or you have no permission to use it."
  exit 1
fi

cd "${ROOT_DIR}"

# Load backend/.env.local early so DATABASE_URL / POSTGRES_* / REDIS_URL are set.
ENV_LOCAL_LOADED=0
if [[ -f "${ENV_LOCAL}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ENV_LOCAL}"
  set +a
  ENV_LOCAL_LOADED=1
  ok "Loaded ${ENV_LOCAL}"
else
  warn "No ${ENV_LOCAL} — will use defaults (set DATABASE_URL for local Postgres)."
fi

# Postgres container name from compose project (default: directory name).
PG_CONTAINER="imperecta-postgres-1"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-imperecta_dev}"

# Resolve container name dynamically if the default doesn't exist.
if ! docker inspect "${PG_CONTAINER}" >/dev/null 2>&1; then
  PG_CONTAINER="$(docker ps --filter "label=com.docker.compose.service=postgres" \
    --filter "label=com.docker.compose.project=imperecta" \
    --format '{{.Names}}' 2>/dev/null | head -1)" || true
fi

wait_for_postgres() {
  local max_attempts=30
  local delay=2
  local attempt=1
  while [[ "${attempt}" -le "${max_attempts}" ]]; do
    echo "${_Y}${_B}⏳${_N} Waiting for PostgreSQL (attempt ${attempt}/${max_attempts})..."

    # Primary check: pg_isready inside the container (bypasses docker compose env_file issues).
    if docker exec "${PG_CONTAINER}" \
      pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
      return 0
    fi

    # Fallback: actual SQL query.
    if docker exec "${PG_CONTAINER}" \
      psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "SELECT 1" >/dev/null 2>&1; then
      return 0
    fi

    if [[ "${attempt}" -lt "${max_attempts}" ]]; then
      sleep "${delay}"
    fi
    attempt=$((attempt + 1))
  done
  return 1
}

info "Starting Postgres + Redis…"
run_compose up -d postgres redis

info "Waiting for PostgreSQL (up to 60s, ${POSTGRES_USER}@${POSTGRES_DB})…"
if ! wait_for_postgres; then
  err "PostgreSQL did not become ready in time."
  echo "${_R}${_B}--- Last 20 lines: docker logs ${PG_CONTAINER} ---${_N}" >&2
  docker logs "${PG_CONTAINER}" --tail 20 2>&1 >&2 || true
  exit 1
fi
ok "PostgreSQL is ready!"

if [[ ! -d "${BACKEND_DIR}" ]]; then
  err "Backend directory not found: ${BACKEND_DIR}"
  exit 1
fi

cd "${BACKEND_DIR}"

if [[ ! -d ".venv" ]]; then
  warn "Creating Python virtual environment (.venv)…"
  python3 -m venv .venv
fi

# shellcheck source=/dev/null
source ".venv/bin/activate"

info "Installing Python dependencies (quiet)…"
"${VENV_PIP}" install --quiet -r requirements.txt
ok "Dependencies are up to date."

info "Running Alembic migrations…"
"${VENV_PY}" -m alembic upgrade head
ok "Database schema is at head."

echo ""
ok "Imperecta Dev Environment готов!"
echo "   ${_B}📡 Backend:${_N}  http://127.0.0.1:8000"
echo "   ${_B}🐘 Postgres:${_N} docker logs -f ${PG_CONTAINER}"
echo "   ${_B}📊 Health:${_N}   http://127.0.0.1:8000/api/health"
echo ""
info "Starting Uvicorn (Ctrl+C to stop)…"
exec "${VENV_PY}" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
