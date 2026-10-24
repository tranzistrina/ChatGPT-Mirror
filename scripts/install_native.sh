#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
command -v python3 >/dev/null || { echo "Python required"; exit 1; }
command -v node >/dev/null || { echo "Node required"; exit 1; }
command -v npm >/dev/null || { echo "npm required"; exit 1; }
command -v caddy >/dev/null || { echo "Caddy required"; exit 1; }
[[ -s .env.native ]] || { echo "Copy .env.native.example to .env.native and edit it"; exit 1; }
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements.txt "gunicorn>=22,<24"
(cd frontend && npm ci --ignore-scripts && npm run build)
echo "Installed. Separate compatible gateway is required."
