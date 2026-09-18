#!/usr/bin/env bash
# Local full-suite runner with the docker test DB (canonical since 2026-09-18).
#
# One-time bootstrap (containers persist afterwards):
#   docker start imperecta-pg-test imperecta-redis-test
#   # fresh DB: see docs/TESTING_LOCAL.md (fake vault + stub pg_cron +
#   # extensions schema + roles, then `alembic upgrade head`)
#
# The full alembic chain 001->062 replays cleanly on an empty DB (verified
# 2026-09-18; 019/022 carry the fresh-replay constraint hygiene).
set -u
cd "$(dirname "$0")/.." || exit 1

if ! pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
  echo "test postgres is not up — run: docker start imperecta-pg-test imperecta-redis-test" >&2
  exit 1
fi

exec env -i HOME="$HOME" PATH="$PATH" PYTHONPATH=. \
 DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/imperecta_test" \
 REDIS_URL="redis://localhost:6379/0" \
 SECRET_KEY=test DATA_FIREWALL_SIGNING_SECRET=test-data-firewall-signing-secret \
 JWT_SECRET=test-jwt-secret JWT_ALGORITHM=HS256 JWT_EXPIRATION_MINUTES=30 \
 JWT_REFRESH_EXPIRATION_DAYS=7 JWT_REFRESH_EXPIRATION_DAYS_REMEMBER=30 \
 MARKET_DATA_TIMEOUT_SECONDS=10 MARKET_DATA_RETRY_ATTEMPTS=2 DECODO_ENABLED=false \
 MARKET_DATA_FOREX_URL="http://localhost:1/inert" MARKET_DATA_CRYPTO_URL="http://localhost:1/inert" \
 CLAUDE_MODEL=auto EMAIL_FROM=test@imperecta.test APP_URL=http://localhost \
 ALLOWED_ORIGINS='["http://localhost"]' APP_ENV=test PORT=8000 \
 PROXY_PROVIDER_API_URL="http://localhost:1/inert" \
 .venv/bin/python -m pytest "$@"
