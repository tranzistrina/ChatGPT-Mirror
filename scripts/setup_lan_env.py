"""Create .env.lan from template with random secrets, preserving existing settings.

Run once: python3 scripts/setup_lan_env.py
Edit the LAN_BIND_IP and LAN_ALLOWED_HOSTS before running Compose.
This script intentionally never prints the generated credentials.
"""
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / ".env.lan"
if target.exists():
    sys.exit("The file .env.lan already exists. I will not overwrite credentials.")
template = (ROOT / ".env.lan.example").read_text(encoding="utf-8")
template = template.replace("REPLACE_WITH_RANDOM_SECRET", secrets.token_hex(48))
template = template.replace("REPLACE_WITH_LONG_RANDOM_PASSWORD", secrets.token_hex(24))
fd = target.open("x", encoding="utf-8")
try:
    fd.write(template)
finally:
    fd.close()
target.chmod(0o600)
print("Created .env.lan with randomly generated secrets. Edit the LAN IPs before launch.")
