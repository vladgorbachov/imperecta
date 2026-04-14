#!/usr/bin/env bash
# Imperecta — stop local dev stack (Docker Compose + native Uvicorn).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

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
warn() { echo "${_Y}${_B}⚠${_N} $*"; }
err()  { echo "${_R}${_B}❌${_N} $*" >&2; }
info() { echo "${_B}▶${_N} $*"; }

run_compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    return 127
  fi
}

info "Stopping Imperecta local environment…"

if docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    run_compose down --remove-orphans 2>/dev/null || true
    ok "Docker Compose stack stopped."
  else
    warn "Docker is not running — skipping compose down."
  fi
else
  err "docker compose / docker-compose not found — skipped container teardown."
fi

info "Stopping Uvicorn processes (if any)…"
UVICORN_KILLED=0
if pkill -f "uvicorn app.main:app" 2>/dev/null; then UVICORN_KILLED=1; fi
if pkill -f "python -m uvicorn app.main:app" 2>/dev/null; then UVICORN_KILLED=1; fi
if [[ "${UVICORN_KILLED}" -eq 1 ]]; then
  ok "Uvicorn processes terminated."
else
  warn "No matching Uvicorn process found (already stopped)."
fi

echo ""
ok "Локальное окружение Imperecta остановлено."
