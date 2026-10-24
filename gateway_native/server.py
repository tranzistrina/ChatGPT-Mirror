"""Experimental, open-source ChatGPT *web* accessToken gateway.

Not an OpenAI Platform API proxy. Does not impersonate browsers, solve CAPTCHA,
forge attestation, or guarantee compatibility with private ChatGPT endpoints.
Everything outbound is restricted to https://chatgpt.com.
"""
from __future__ import annotations

import base64
from collections import defaultdict
from dataclasses import dataclass, field
from hashlib import sha256
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import requests

ROOT = Path(__file__).resolve().parent
UPSTREAM = "https://chatgpt.com"
PORT = int(os.environ.get("GATEWAY_PORT", "8787"))
HOST = os.environ.get("GATEWAY_HOST", "127.0.0.1")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
WEB_MODEL = os.environ.get("CHATGPT_WEB_MODEL", "auto")
BIND_IP = os.environ.get("LAN_BIND_IP", "127.0.0.1")
LAN_PORT = int(os.environ.get("LAN_PORT", "50002"))
COOKIE_NAME = "user-gateway-token"
TTL = 12 * 3600
MAX_MESSAGE = 6000
MAX_BODY = 20_000
MAX_STREAM = 6_000_000
ALLOWED_ORIGINS = {
    f"http://{BIND_IP}:{LAN_PORT}",
    "http://127.0.0.1:50002",
    "http://localhost:50002",
}
if os.environ.get("GATEWAY_ALLOWED_ORIGINS"):
    ALLOWED_ORIGINS = set(os.environ["GATEWAY_ALLOWED_ORIGINS"].split(","))


class GatewayError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(message)


@dataclass
class Session:
    username: str
    access_token: str = field(repr=False)
    expires: float = 0
    conversations: set[str] = field(default_factory=set)


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.sessions: dict[str, Session] = {}
        self.accounts: dict[str, str] = {}  # token cache; process memory only
        self.history = defaultdict(list)
        self.slots = threading.BoundedSemaphore(3)

    def create(self, username: str, access_token: str) -> str:
        key = secrets.token_urlsafe(32)
        with self.lock:
            now = time.time()
            self.sessions = {k: v for k, v in self.sessions.items() if v.expires > now}
            if len(self.sessions) >= 200:
                raise GatewayError(429, "Too many concurrent local sessions")
            self.sessions[key] = Session(username, access_token, now + TTL)
        return key

    def get(self, key: str) -> Session | None:
        with self.lock:
            entry = self.sessions.get(key)
            if not entry:
                return None
            if entry.expires < time.time():
                self.sessions.pop(key, None)
                return None
            return entry

    def revoke_user(self, username: str) -> None:
        with self.lock:
            for k in [k for k, v in self.sessions.items() if v.username == username]:
                self.sessions.pop(k, None)


def claims_from_jwt(token: str) -> dict:
    """Read only display metadata AFTER upstream has authenticated the token.

    No JWT signature is verified here; decoded claims must never authorize access.
    """
    try:
        bits = token.split(".")
        if len(bits) != 3 or len(bits[1]) > 16000:
            return {}
        data = base64.urlsafe_b64decode(bits[1] + "=" * (-len(bits[1]) % 4))
        obj = json.loads(data)
        return obj if isinstance(obj, dict) else {}
    except (ValueError, UnicodeError):
        return {}


def upstream_headers(access_token: str, accept: str = "application/json") -> dict:
    return {
        "Authorization": "Bearer " + access_token,
        "Accept": accept,
        "Content-Type": "application/json",
        "User-Agent": "ChatGPT-Mirror-Open-Gateway/0.1",
    }


def validate_token(token: str) -> dict:
    if not isinstance(token, str) or not 20 < len(token) < 16000 or "\n" in token:
        raise GatewayError(400, "Expected a valid ChatGPT web accessToken")
    try:
        res = requests.get(
            UPSTREAM + "/backend-api/models",
            headers=upstream_headers(token),
            timeout=(10, 25),
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise GatewayError(502, "Cannot reach ChatGPT from the server") from exc
    if res.status_code in (401, 403):
        raise GatewayError(401, "ChatGPT rejected accessToken or requires additional web verification")
    if res.status_code != 200:
        raise GatewayError(502, f"ChatGPT model check returned HTTP {res.status_code}")
    claims = claims_from_jwt(token)
    profile = claims.get("https://api.openai.com/profile", {})
    if not isinstance(profile, dict):
        profile = {}
    email = profile.get("email") or claims.get("email")
    if not isinstance(email, str) or not email or len(email) > 64:
        # Use a stable non-email account identifier rather than inventing an address.
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub:
            sub = sha256(token.encode()).hexdigest()[:20]
        email = "account-" + sha256(sub.encode()).hexdigest()[:20]
    plan = claims.get("plan_type") or "unknown"
    if not isinstance(plan, str) or len(plan) > 32:
        plan = "unknown"
    return {"user_info": {"email": email, "plan_type": plan}, "access_token": token}


def stream_conversation(session: Session, message: str, conv: str | None, parent: str | None):
    """Yield (text, conversation_id, parent_message_id, handoff_detected).

    May fail on modern ChatGPT: Sentinel/Conduit tokens and stream handoffs are
    private and intentionally not bypassed. Callers surface a clear error.
    """
    if conv and conv not in session.conversations:
        raise GatewayError(403, "Conversation does not belong to this local session")
    if bool(conv) != bool(parent):
        raise GatewayError(400, "conversation_id and parent_message_id must be provided together")
    message_id = str(uuid4())
    body = {
        "action": "next",
        "messages": [{
            "id": message_id,
            "author": {"role": "user"},
            "content": {"content_type": "text", "parts": [message]},
        }],
        "parent_message_id": parent or "client-created-root",
        "model": WEB_MODEL,
        "conversation_mode": {"kind": "primary_assistant"},
        "timezone": "UTC",
        "timezone_offset_min": 0,
    }
    if conv:
        body["conversation_id"] = conv
    try:
        upstream = requests.post(
            UPSTREAM + "/backend-api/f/conversation",
            headers=upstream_headers(session.access_token, "text/event-stream"),
            json=body,
            stream=True,
            timeout=(10, 120),
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise GatewayError(502, "Connection to ChatGPT failed") from exc

    if upstream.status_code in (401, 403):
        upstream.close()
        raise GatewayError(502, "ChatGPT refused the request: accessToken alone may be insufficient (Sentinel/verification required)")
    if upstream.status_code != 200:
        code = upstream.status_code
        upstream.close()
        raise GatewayError(502, f"ChatGPT conversation endpoint returned HTTP {code}")

    current_conv = conv
    last_parent = parent
    handoff = False
    text = ""
    transferred = 0
    try:
        for line in upstream.iter_lines(decode_unicode=False):
            if not line:
                continue
            transferred += len(line)
            if transferred > MAX_STREAM:
                raise GatewayError(502, "Upstream response exceeded the safety limit")
            if not line.startswith(b"data: "):
                continue
            payload = line[6:]
            if payload == b"[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except (ValueError, UnicodeError):
                continue
            if not isinstance(chunk, dict):
                continue
            c = chunk.get("conversation_id")
            if isinstance(c, str) and c:
                current_conv = c
            if chunk.get("type") == "stream_handoff":
                handoff = True
            msg = chunk.get("message")
            if not isinstance(msg, dict) or (msg.get("author") or {}).get("role") != "assistant":
                continue
            part = (msg.get("content") or {}).get("parts") or []
            candidate = "\n".join(p for p in part if isinstance(p, str))
            if candidate and candidate != text:
                text = candidate
                if isinstance(msg.get("id"), str):
                    last_parent = msg["id"]
                yield (text, current_conv, last_parent, handoff)
    except (requests.RequestException, ValueError) as exc:
        raise GatewayError(502, "ChatGPT response stream ended unexpectedly") from exc
    finally:
        upstream.close()
    # Modern streams can hand off to WebSockets. No unsafe fake response.
    if not text and handoff:
        raise GatewayError(501, "ChatGPT requires a stream handoff (SSE/WebSocket), not yet supported by this gateway")
    if not text:
        raise GatewayError(502, "ChatGPT returned no usable answer; protocol may have changed")
    if current_conv:
        session.conversations.add(current_conv)
    yield (text, current_conv, last_parent, handoff)


class Handler(BaseHTTPRequestHandler):
    server_version = "OpenMirror/0.1"

    @property
    def state(self) -> State:
        return self.server.state

    def log_message(self, fmt: str, *args) -> None:
        # URLs in this service must not contain credentials (see /api/not-login).
        # Do not log the request target, because mirror URLs contain a bearer token.
        print(f"[gateway] {self.command} status={args[1] if len(args)>1 else '-'}")

    def cookie_token(self) -> str:
        try:
            c = cookies.SimpleCookie()
            c.load(self.headers.get("Cookie", ""))
            return c[COOKIE_NAME].value if COOKIE_NAME in c else ""
        except cookies.CookieError:
            return ""

    def admin(self) -> None:
        value = self.headers.get("Authorization", "")
        expected = "Bearer " + ADMIN_PASSWORD
        if not ADMIN_PASSWORD or not hmac.compare_digest(value.encode(), expected.encode()):
            raise GatewayError(401, "Internal Django authentication failed")

    def session(self) -> Session:
        s = self.state.get(self.cookie_token())
        if not s:
            raise GatewayError(401, "Sign in through the administration panel first")
        return s

    def json_body(self, *, enforce_origin=False) -> dict:
        if enforce_origin and self.headers.get("Origin") not in ALLOWED_ORIGINS:
            raise GatewayError(403, "Invalid browser origin")
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            raise GatewayError(415, "JSON is required")
        try:
            size = int(self.headers.get("Content-Length", "-1"))
        except ValueError as exc:
            raise GatewayError(400, "Invalid Content-Length") from exc
        if not 1 <= size <= MAX_BODY:
            raise GatewayError(413, "Request body must be 1..20000 bytes")
        try:
            value = json.loads(self.rfile.read(size))
        except (ValueError, UnicodeError) as exc:
            raise GatewayError(400, "Invalid JSON") from exc
        if not isinstance(value, dict):
            raise GatewayError(400, "JSON object required")
        return value

    def headers_common(self, data: bytes, mime: str) -> None:
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; form-action 'self'; frame-ancestors 'none'")
    def send_json(self, code: int, value) -> None:
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(code)
        self.headers_common(data, "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            p = urlsplit(self.path)
            if p.path == "/healthz":
                return self.send_json(200, {"status": "ok", "provider": "ChatGPT web (experimental)"})
            if p.path == "/api/whoami":
                ses = self.state.get(self.cookie_token())
                return self.send_json(200, {
                    "authenticated": bool(ses),
                    "username": ses.username if ses else None,
                    "model": WEB_MODEL,
                })
            if p.path == "/api/not-login":
                args = parse_qs(p.query)
                key = (args.get("user_gateway_token") or [""])[0]
                if not self.state.get(key):
                    raise GatewayError(401, "Invalid or expired mirror token")
                self.send_response(302)
                self.send_header("Location", "/")
                # Old Vue admin creates its own JS cookie. We can set HttpOnly
                # here for mirror links to avoid exposing the token to JS.
                self.send_header("Set-Cookie", f"{COOKIE_NAME}={key}; HttpOnly; Path=/; SameSite=Strict; Max-Age={TTL}")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                return
            paths = {"/": ("index.html", "text/html; charset=utf-8"),
                     "/app.js": ("app.js", "application/javascript; charset=utf-8"),
                     "/style.css": ("style.css", "text/css; charset=utf-8")}
            if p.path in paths:
                file, mime = paths[p.path]
                data = (ROOT / file).read_bytes()
                self.send_response(200)
                self.headers_common(data, mime)
                self.end_headers()
                self.wfile.write(data)
                return
            raise GatewayError(404, "Not found")
        except GatewayError as exc:
            self.send_json(exc.status, {"error": str(exc)})

    def do_POST(self):
        try:
            p = urlsplit(self.path)
            internal = p.path.startswith("/api/") and p.path not in ("/api/chat",)
            if internal:
                self.admin()
                data = self.json_body()
                return self.handle_internal(p.path, data)
            if p.path != "/api/chat":
                raise GatewayError(404, "Not found")
            ses = self.session()
            data = self.json_body(enforce_origin=True)
            message = data.get("message")
            conv = data.get("conversation_id")
            parent = data.get("parent_message_id")
            if not isinstance(message, str) or not 0 < len(message.strip()) <= MAX_MESSAGE:
                raise GatewayError(400, "Message must contain 1 to 6000 characters")
            if conv is not None and (not isinstance(conv, str) or len(conv) > 128):
                raise GatewayError(400, "Invalid conversation_id")
            if parent is not None and (not isinstance(parent, str) or len(parent) > 128):
                raise GatewayError(400, "Invalid parent_message_id")
            if not self.state.slots.acquire(blocking=False):
                raise GatewayError(429, "Server is busy")
            try:
                # Start upstream before sending SSE headers, so HTTP errors
                # reach clients as proper status codes, not fake chat events.
                gen = stream_conversation(ses, message.strip(), conv, parent)
                try:
                    first = next(gen)
                except StopIteration:
                    raise GatewayError(502, "ChatGPT stream was empty")
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.send_event("reply", first)
                for event in gen:
                    self.send_event("reply", event)
                self.send_event("done", {})
            except GatewayError:
                raise
            except (BrokenPipeError, ConnectionResetError):
                return
            finally:
                self.state.slots.release()
        except GatewayError as exc:
            try:
                self.send_json(exc.status, {"error": str(exc)})
            except (BrokenPipeError, ConnectionResetError):
                pass

    def send_event(self, kind: str, data) -> None:
        if isinstance(data, tuple):
            text, cid, mid, _ = data
            data = {"text": text, "conversation_id": cid, "parent_message_id": mid}
        self.wfile.write(("event: " + kind + "\ndata: " + json.dumps(data, ensure_ascii=False) + "\n\n").encode())
        self.wfile.flush()

    def handle_internal(self, path: str, data: dict):
        if path == "/api/get-user-info":
            token = data.get("chatgpt_token")
            details = validate_token(token)
            self.state.accounts[details["user_info"]["email"]] = token
            return self.send_json(200, details)
        if path == "/api/close-chatgpt-memory":
            # Explicitly unsupported, do NOT pretend ChatGPT memory was changed.
            return self.send_json(200, {"status": "unsupported", "message": "Memory setting was not changed"})
        if path == "/api/login":
            user, access_token = data.get("user_name"), data.get("access_token")
            if not isinstance(user, str) or not 0 < len(user) <= 120:
                raise GatewayError(400, "Invalid local username")
            if not isinstance(access_token, str) or not 20 < len(access_token) < 16000:
                raise GatewayError(400, "Invalid accessToken")
            key = self.state.create(user, access_token)
            return self.send_json(200, {"user-gateway-token": key})
        if path == "/api/logout":
            user = data.get("user_name")
            if not isinstance(user, str):
                raise GatewayError(400, "Invalid user")
            self.state.revoke_user(user)
            return self.send_json(200, {"status": "ok"})
        if path == "/api/get-chatgpt-use-count":
            return self.send_json(200, {})
        if path == "/api/get-user-use-count":
            return self.send_json(200, {})
        if path == "/api/get-mirror-token":
            # Only generate links for sessions that are already activated.
            # Unlike the closed gateway, this prototype has no persistent
            # token/account mapping across restarts.
            name = data.get("user_name")
            names = data.get("chatgpt_list")
            if not isinstance(name, str) or not isinstance(names, list):
                raise GatewayError(400, "Invalid mirror token request")
            if len(names) > 100 or any(not isinstance(n, str) for n in names):
                raise GatewayError(400, "Invalid account list")
            return self.send_json(200, [])  # not implemented; fail closed
        raise GatewayError(404, "Not found")


def main():
    if not ADMIN_PASSWORD or ADMIN_PASSWORD == "REPLACE_WITH_LONG_RANDOM_PASSWORD" or len(ADMIN_PASSWORD) < 16:
        raise SystemExit("ADMIN_PASSWORD must be a unique 16+ character secret")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    httpd.state = State()
    print(f"Open accessToken gateway listening at {HOST}:{PORT}; model={WEB_MODEL}; experimental.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
