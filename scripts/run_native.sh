#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.native ]] || { echo ".env.native missing"; exit 1; }
set -a
source .env.native
set +a
[[ "$DJANGO_ENV" == "PRODUCTION" ]] || { echo "Set DJANGO_ENV=PRODUCTION"; exit 1; }
[[ -n "$DJANGO_SECRET_KEY" && "$DJANGO_SECRET_KEY" != "REPLACE_WITH_RANDOM_SECRET" ]] || { echo "Set DJANGO_SECRET_KEY"; exit 1; }
[[ -n "$ADMIN_PASSWORD" && "$ADMIN_PASSWORD" != "REPLACE_WITH_LONG_RANDOM_PASSWORD" ]] || { echo "Set ADMIN_PASSWORD"; exit 1; }
[[ -n "$CHATGPT_GATEWAY_URL" && -n "$GATEWAY_UPSTREAM" ]] || { echo "Set gateway variables"; exit 1; }
(cd backend && ../.venv/bin/python manage.py migrate --noinput && ../.venv/bin/python cli/create_init_user.py)
(cd backend && ../.venv/bin/gunicorn app.wsgi:application --bind 127.0.0.1:8000 --workers 2) &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT INT TERM
caddy run --config ./Caddyfile.native
