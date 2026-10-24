#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.native ]] || { echo ".env.native missing"; exit 1; }
set -a
source .env.native
set +a
[[ "${DJANGO_ENV:-}" == "PRODUCTION" ]] || { echo "Set DJANGO_ENV=PRODUCTION"; exit 1; }
[[ -n "${DJANGO_SECRET_KEY:-}" && "$DJANGO_SECRET_KEY" != "REPLACE_WITH_RANDOM_SECRET" ]] || { echo "Set DJANGO_SECRET_KEY"; exit 1; }
[[ -n "${ADMIN_PASSWORD:-}" && "$ADMIN_PASSWORD" != "REPLACE_WITH_LONG_RANDOM_PASSWORD" ]] || { echo "Set ADMIN_PASSWORD"; exit 1; }
[[ -n "${CHATGPT_GATEWAY_URL:-}" && -n "${GATEWAY_UPSTREAM:-}" ]] || { echo "Set gateway URL variables"; exit 1; }
gateway_password="${GATEWAY_ACCESS_PASSWORD:-}"
[[ ${#gateway_password} -ge 16 && "$gateway_password" != "REPLACE_WITH_GATEWAY_PASSWORD" ]] || { echo "Set strong GATEWAY_ACCESS_PASSWORD"; exit 1; }

(cd backend && ../.venv/bin/python manage.py migrate --noinput && ../.venv/bin/python cli/create_init_user.py)
# Gateway binds to loopback only; no public port exposed.
GATEWAY_HOST=127.0.0.1 .venv/bin/python gateway/server.py &
gateway_pid=$!
(cd backend && ../.venv/bin/gunicorn app.wsgi:application --bind 127.0.0.1:8000 --workers 2) &
backend_pid=$!
cleanup() {
  kill "$backend_pid" "$gateway_pid" 2>/dev/null || true
  wait "$backend_pid" "$gateway_pid" 2>/dev/null || true
}
trap cleanup EXIT
caddy run --config ./Caddyfile.native
