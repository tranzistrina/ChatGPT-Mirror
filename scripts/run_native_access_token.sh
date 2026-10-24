#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.native ]] || { echo "Missing .env.native"; exit 1; }
set -a
source .env.native
set +a
[[ "${DJANGO_ENV:-}" == "PRODUCTION" ]] || { echo "Set DJANGO_ENV=PRODUCTION"; exit 1; }
secret="${DJANGO_SECRET_KEY:-}"
[[ ${#secret} -ge 32 ]] || { echo "Generate DJANGO_SECRET_KEY"; exit 1; }
password="${ADMIN_PASSWORD:-}"
[[ ${#password} -ge 16 ]] || { echo "Generate ADMIN_PASSWORD"; exit 1; }
[[ -n "${LAN_BIND_IP:-}" ]] || { echo "Set LAN_BIND_IP to your Mac's LAN IP"; exit 1; }
export CHATGPT_GATEWAY_URL="http://127.0.0.1:8787"
export GATEWAY_HOST=127.0.0.1
export GATEWAY_PORT=8787
export LAN_PORT=50002
(cd backend && ../.venv/bin/python manage.py migrate --noinput && ../.venv/bin/python cli/create_init_user.py)
.venv/bin/python gateway_native/server.py &
gateway_pid=$!
(cd backend && ../.venv/bin/gunicorn app.wsgi:application --bind 127.0.0.1:8000 --workers 2) &
django_pid=$!
cleanup() {
  kill "$gateway_pid" "$django_pid" 2>/dev/null || true
  wait "$gateway_pid" "$django_pid" 2>/dev/null || true
}
trap cleanup EXIT
caddy run --config ./Caddyfile.native.lan
