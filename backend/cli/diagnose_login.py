"""Local admin sign-in diagnostic.

Runs *inside the Django web container*, using its real environment and DB.
Never prints ADMIN_PASSWORD, password hashes, auth tokens, or web accessTokens.
The in-process test client makes one login request only when the password matches.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

import django
django.setup()

from django.conf import settings
from django.test import Client
from django.utils import timezone
from app.accounts.models import User


def check_proxy(username: str, password: str, host: str) -> int:
    """Test the real HTTP route Caddy -> Django, suppressing bearer tokens."""
    from urllib import request as urllib_request
    from urllib.error import HTTPError, URLError

    data = json.dumps({"username": username, "password": password}).encode()
    req = urllib_request.Request(
        "http://127.0.0.1:50002/0x/user/login",
        data=data,
        headers={
            "Host": f"{host}:50002",
            "Content-Type": "application/json",
            "User-Agent": "MirrorAdminDiagnostic/1",
        },
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=8) as response:
            status = response.status
            body = response.read(32768)
    except HTTPError as exc:
        print("Real Caddy login HTTP status:", exc.code)
        print("RESULT: PROXY_LOGIN_FAILED. Check Caddyfile and logs.")
        return 10
    except (URLError, OSError) as exc:
        print("RESULT: CADDY_UNREACHABLE.", type(exc).__name__)
        return 11
    try:
        payload = json.loads(body)
    except ValueError:
        payload = {}
    print("Real Caddy login HTTP status:", status)
    if status == 200 and isinstance(payload, dict) and payload.get("is_admin") and payload.get("admin_token"):
        print("RESULT: PROXY_LOGIN_OK. Browser login should work; inspect UI state or cache if not.")
        return 0
    print("RESULT: PROXY_LOGIN_INVALID_RESPONSE (auth details suppressed).")
    return 12


def diagnose() -> int:
    username = os.environ.get("ADMIN_USERNAME", "")
    insecure_test = os.environ.get("MIRROR_UNSAFE_ADMIN_TEST_LOGIN") == "true"
    password = "12345" if insecure_test else os.environ.get("ADMIN_PASSWORD", "")
    print("=== Mirror administrator diagnostic (secrets hidden) ===")
    print("Configured username:", username or "(missing)")
    print("Temporary fixed admin / 12345 mode:", "ON" if insecure_test else "OFF")
    print("Expected local password configured:", "YES" if password else "NO")
    print("Database:", Path(settings.DATABASES["default"]["NAME"]).name)
    print("Production mode:", "YES" if settings.DEBUG is False else "NO")
    if not username or not password:
        print("RESULT: Missing ADMIN_USERNAME or ADMIN_PASSWORD in the container.")
        return 2
    try:
        user = User.objects.filter(username=username).first()
    except Exception as exc:
        print("RESULT: Database unavailable or migrations incomplete.")
        print("Error type:", type(exc).__name__)
        return 3
    if user is None:
        print("Administrator exists in database: NO")
        print("RESULT: Run 'python cli/create_init_user.py' inside the SAME web container.")
        return 4
    print("Administrator exists in database: YES")
    print("Active:", "YES" if user.is_active else "NO")
    print("Staff:", "YES" if user.is_staff else "NO")
    print("Superuser:", "YES" if user.is_superuser else "NO")
    matches = user.check_password(password)
    print("Password matches container environment:", "YES" if matches else "NO")
    if not matches:
        print("RESULT: Password in database differs from ADMIN_PASSWORD currently in container.")
        return 5
    if not user.is_active or not user.is_staff:
        print("RESULT: Account is not active/staff. Reinitialize admin from environment.")
        return 6
    if user.expired_date:
        print("Account expiration check:", "EXPIRED" if user.expired_date <= timezone.localdate() else "VALID")
        if user.expired_date <= timezone.localdate():
            return 7
    # Host selected from Django configuration. No request data leaves the container.
    allowed = settings.ALLOWED_HOSTS
    host = next((h for h in allowed if h not in ("*",)), "localhost")
    client = Client(HTTP_HOST=host, HTTP_USER_AGENT="MirrorAdminDiagnostic/1")
    try:
        response = client.post(
            "/0x/user/login",
            data=json.dumps({"username": username, "password": password}),
            content_type="application/json",
        )
    except Exception as exc:
        print("RESULT: Django API crashed on login.")
        print("Error type:", type(exc).__name__)
        return 8
    print("Internal Django login HTTP status:", response.status_code)
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code == 200 and isinstance(payload, dict) and payload.get("admin_token"):
        print("Django returned admin token: YES (token value hidden)")
        print("Django recognized admin:","YES" if payload.get("is_admin") else "NO")
        if payload.get("is_admin"):
            print("RESULT: DJANGO_LOGIN_OK. Checking the real Caddy reverse proxy...")
            return check_proxy(username, password, host)
    if isinstance(payload, dict):
        print("Error fields:", ", ".join(sorted(str(k) for k in payload)) or "(none)")
    print("RESULT: Django login failed in-process; inspect 'docker compose logs web'.")
    return 9


if __name__ == "__main__":
    raise SystemExit(diagnose())
