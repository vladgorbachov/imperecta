#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@imperecta.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

login_payload="$(python3 - "${ADMIN_EMAIL}" "${ADMIN_PASSWORD}" <<'PY'
import json
import sys

payload = {
    "email": sys.argv[1],
    "password": sys.argv[2],
}
print(json.dumps(payload, ensure_ascii=False))
PY
)"

token_response="$(curl -fsS \
  -X POST "${API_BASE_URL}/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "${login_payload}")"

access_token="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("access_token",""))' <<< "${token_response}")"

if [[ -z "${access_token}" ]]; then
  echo "Failed to get admin access token." >&2
  exit 1
fi

clear_response="$(curl -fsS \
  -X POST "${API_BASE_URL}/api/admin/products/clear-pool" \
  -H "Authorization: Bearer ${access_token}" \
  -H "Content-Type: application/json")"

status="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("status",""))' <<< "${clear_response}")"

if [[ "${status}" != "pool_cleared" ]]; then
  echo "Pool clear endpoint returned unexpected response: ${clear_response}" >&2
  exit 1
fi

echo "БД полностью очищена от маркетплейсов и товаров"
