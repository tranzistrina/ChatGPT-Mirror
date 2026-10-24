#!/usr/bin/env python3
"""Generate dedicated, private LAN browser credentials without changing .env.lan.

The remote Chromium service uses LinuxServer's built-in HTTPS and Basic Auth.
This setup never stores or asks for ChatGPT accessTokens or OpenAI API keys.
"""
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / ".env.browser-relay"


def main() -> int:
    if DEST.exists():
        print("Already exists:", DEST)
        print("Existing credentials preserved. View locally with: cat .env.browser-relay")
        return 0
    password = secrets.token_urlsafe(30)
    data = (
        "# ChatGPT LAN remote-browser authentication, not a ChatGPT password\n"
        "LAN_BIND_IP=192.168.0.100\n"
        "LAN_PORT=50002\n"
        "BROWSER_USER=mirror\n"
        f"BROWSER_PASSWORD={password}\n"
        "TZ=Europe/Rome\n"
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(DEST, flags, 0o600)
    except FileExistsError:
        print("Already exists:", DEST)
        return 0
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(data)
    except Exception:
        try:
            DEST.unlink()
        finally:
            raise
    print("Created private credentials:", DEST)
    print("LAN site: https://192.168.0.100:50002/")
    print("Login: mirror")
    print("Password: use 'cat .env.browser-relay' locally to see it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
