"""Offline regression tests for the one-password LAN Chromium launcher."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "scripts" / "setup_browser_relay.py"


class SetupTests(unittest.TestCase):
    def test_new_secrets_are_private_and_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            workspace = Path(t)
            (workspace / "scripts").mkdir()
            script = workspace / "scripts" / SETUP.name
            shutil.copyfile(SETUP, script)

            first = subprocess.run([sys.executable, str(script)], check=True,
                                   text=True, capture_output=True)
            env = workspace / ".env.browser-relay"
            data = env.read_text()
            self.assertIn("Created private credentials", first.stdout)
            self.assertIn("LAN_BIND_IP=192.168.0.100", data)
            self.assertIn("LAN_PORT=50002", data)
            self.assertIn("BROWSER_USER=mirror", data)
            self.assertNotIn("REPLACE_WITH", data)
            pw = next(x.split("=", 1)[1] for x in data.splitlines()
                      if x.startswith("BROWSER_PASSWORD="))
            self.assertGreaterEqual(len(pw), 30)
            if os.name == "posix":
                self.assertEqual(env.stat().st_mode & 0o077, 0)
            second = subprocess.run([sys.executable, str(script)], check=True,
                                    text=True, capture_output=True)
            self.assertIn("Already exists", second.stdout)
            self.assertEqual(env.read_text(), data)

    def test_password_is_not_in_source_control(self):
        ignores = (ROOT / ".gitignore").read_text()
        self.assertIn(".env.browser-relay", ignores)
        script = SETUP.read_text()
        self.assertIn("secrets.token_urlsafe", script)


if __name__ == "__main__":
    unittest.main()
