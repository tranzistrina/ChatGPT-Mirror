"""Small, auditable local gateway for the official OpenAI Responses API.

This is NOT a reverse-engineered ChatGPT web gateway and does not emulate
chat.openai.com sessions or the original closed-source protocol.
"""
from __future__ import annotations

from collections import deque
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import secrets
import threading
import time
from urllib import error, request

ROOT = Path(__file__).resolve().parent
SESSION_LIFETIME = 12 * 60 * 60
MAX_BODY_BYTES = 48 * 1024
MAX_MESSAGES = 20
MAX_MESSAGE_CHARS = 6000
MAX_TOTAL_CHARS = 24000
COOKIE = "mirror_gateway_session"
ORIGINS = set(os.environ.get(
    "GATEWAY_ALLOWED_ORIGINS",
    "http://127.0.0.1:50002,http://localhost:50002"
).split(","))
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
PASSWORD = os.environ.get("GATEWAY_ACCESS_PASSWORD", "").strip()
COOKIE_SECURE = os.environ.get("GATEWAY_COOKIE_SECURE", "false").lower() == "true"
PORT = int(os.environ.get("GATEWAY_PORT", "8787"))
HOST = os.environ.get("GATEWAY_HOST", "127.0.0.1")


class ClientError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.sessions: dict[str, float] = {}
        self.failed_logins: deque[float] = deque()
        self.api_slots = threading.BoundedSemaphore(value=2)

    def new_session(self) -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self.lock:
            self.sessions = {k: v for k, v in self.sessions.items() if v > now}
            self.sessions[token] = now + SESSION_LIFETIME
        return token

    def has_session(self, token: str) -> bool:
        if not token:
            return False
        with self.lock:
            deadline = self.sessions.get(token, 0)
            if deadline <= time.time():
                self.sessions.pop(token, None)
                return False
            return True

    def remove_session(self, token: str) -> None:
        with self.lock:
            self.sessions.pop(token, None)

    def allow_login_attempt(self) -> bool:
        now = time.time()
        with self.lock:
            while self.failed_logins and self.failed_logins[0] < now - 600:
                self.failed_logins.popleft()
            return len(self.failed_logins) < 10

    def failed_login(self) -> None:
        with self.lock:
            self.failed_logins.append(time.time())


def validate_messages(payload: object) -> list[dict[str, str]]:
    if not isinstance(payload, dict) or set(payload) != {"messages"}:
        raise ClientError(400, "Expected a messages array.")
    messages = payload["messages"]
    if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_MESSAGES:
        raise ClientError(400, "Message history must contain 1 to 20 messages.")
    total = 0
    clean = []
    for item in messages:
        if not isinstance(item, dict) or set(item) != {"role", "content"}:
            raise ClientError(400, "Invalid message format.")
        role, content = item["role"], item["content"]
        if role not in ("user", "assistant") or not isinstance(content, str):
            raise ClientError(400, "Invalid message role or content.")
        if not content.strip() or len(content) > MAX_MESSAGE_CHARS:
            raise ClientError(400, "Message must contain 1 to 6000 characters.")
        total += len(content)
        clean.append({"role": role, "content": content})
    if total > MAX_TOTAL_CHARS or clean[-1]["role"] != "user":
        raise ClientError(400, "Conversation is too long or last message is not from the user.")
    return clean


def extract_text(data: object) -> str:
    if not isinstance(data, dict):
        raise ClientError(502, "Invalid response from the AI provider.")
    parts = []
    for item in data.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if isinstance(part, dict) and part.get("type") == "output_text":
                value = part.get("text")
                if isinstance(value, str):
                    parts.append(value)
    text = "\n".join(parts).strip()
    if not text:
        raise ClientError(502, "The model returned no text. Try again.")
    return text


def ask_openai(messages: list[dict[str, str]]) -> str:
    if not API_KEY or API_KEY == "REPLACE_WITH_OPENAI_API_KEY":
        raise ClientError(503, "Set OPENAI_API_KEY in the server environment.")
    body = json.dumps({
        "model": MODEL,
        "input": messages,
        "store": False,
        "max_output_tokens": 900,
    }).encode("utf-8")
    req = request.Request(
        "https://api.openai.com/v1/responses",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + API_KEY},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=80) as response:
            if response.status != 200:
                raise ClientError(502, "Unexpected AI provider response.")
            data = json.load(response)
    except error.HTTPError as exc:
        # Do not return provider response bodies (possible account metadata).
        if exc.code in (401, 403):
            raise ClientError(502, "OpenAI rejected the API key or project permissions.") from exc
        if exc.code == 429:
            raise ClientError(429, "OpenAI rate limit or account quota reached.") from exc
        raise ClientError(502, "OpenAI API request failed (HTTP %d)." % exc.code) from exc
    except (error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ClientError(502, "Cannot reach OpenAI. Check the connection.") from exc
    return extract_text(data)


class Handler(BaseHTTPRequestHandler):
    server_version = "MirrorGateway/1.0"
    state: State

    def log_message(self, format: str, *args: object) -> None:
        # Avoid logging sensitive request bodies or cookies.
        print("%s [%s] %s" % (self.client_address[0], self.log_date_time_string(), format % args))

    def headers_common(self, length: int, mime: str = "application/json; charset=utf-8") -> None:
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self'; form-action 'self'; "
            "frame-ancestors 'none'; base-uri 'none'",
        )

    def send_json(self, code: int, value: dict, cookie: str | None = None) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.headers_common(len(body))
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def session_token(self) -> str:
        try:
            jar = cookies.SimpleCookie()
            jar.load(self.headers.get("Cookie", ""))
            morsel = jar.get(COOKIE)
            return morsel.value if morsel else ""
        except cookies.CookieError:
            return ""

    def cookie_header(self, token: str, clear: bool = False) -> str:
        value = f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict"
        value += "; Secure" if COOKIE_SECURE else ""
        value += "; Max-Age=0" if clear else f"; Max-Age={SESSION_LIFETIME}"
        return value

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/healthz":
            self.send_json(200, {"status": "ok"})
        elif path == "/api/session":
            self.send_json(200, {
                "authenticated": self.state.has_session(self.session_token()),
                "configured": bool(API_KEY and API_KEY != "REPLACE_WITH_OPENAI_API_KEY"),
                "model": MODEL,
            })
        elif path in ("/", "/app.js", "/style.css"):
            name = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}[path]
            mime = "text/html; charset=utf-8" if path == "/" else (
                "application/javascript; charset=utf-8" if path.endswith(".js") else "text/css; charset=utf-8"
            )
            data = (ROOT / name).read_bytes()
            self.send_response(200)
            self.headers_common(len(data), mime)
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_json(404, {"error": "Not found."})

    def read_payload(self) -> object:
        if self.headers.get("Origin") not in ORIGINS:
            raise ClientError(403, "Invalid request origin.")
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise ClientError(415, "Content-Type must be application/json.")
        try:
            size = int(self.headers.get("Content-Length", "-1"))
        except ValueError as exc:
            raise ClientError(400, "Invalid Content-Length.") from exc
        if not 0 <= size <= MAX_BODY_BYTES:
            raise ClientError(413, "Request is too large.")
        try:
            return json.loads(self.rfile.read(size))
        except (ValueError, UnicodeError) as exc:
            raise ClientError(400, "Invalid JSON.") from exc

    def do_POST(self) -> None:
        try:
            payload = self.read_payload()
            if self.path == "/api/login":
                if not self.state.allow_login_attempt():
                    raise ClientError(429, "Too many unsuccessful logins. Try later.")
                if not isinstance(payload, dict) or not isinstance(payload.get("password"), str):
                    raise ClientError(400, "Password required.")
                if len(payload["password"]) > 1024:
                    raise ClientError(400, "Password too long.")
                if not hmac.compare_digest(payload["password"].encode(), PASSWORD.encode()):
                    self.state.failed_login()
                    raise ClientError(401, "Incorrect password.")
                token = self.state.new_session()
                self.send_json(200, {"authenticated": True}, self.cookie_header(token))
                return
            token = self.session_token()
            if not self.state.has_session(token):
                raise ClientError(401, "Login required.")
            if self.path == "/api/logout":
                self.state.remove_session(token)
                self.send_json(200, {"authenticated": False}, self.cookie_header("", clear=True))
                return
            if self.path != "/api/chat":
                raise ClientError(404, "Not found.")
            messages = validate_messages(payload)
            if not self.state.api_slots.acquire(blocking=False):
                raise ClientError(429, "The chat is busy. Retry shortly.")
            try:
                reply = ask_openai(messages)
            finally:
                self.state.api_slots.release()
            self.send_json(200, {"reply": reply, "model": MODEL})
        except ClientError as exc:
            self.send_json(exc.status, {"error": str(exc)})
        except Exception:
            # Fail closed without leaking stack traces or credentials.
            self.send_json(500, {"error": "Internal gateway error."})


def main() -> None:
    if not PASSWORD or PASSWORD == "REPLACE_WITH_GATEWAY_PASSWORD":
        raise SystemExit("Set a strong GATEWAY_ACCESS_PASSWORD (see setup guide).")
    if len(PASSWORD) < 16:
        raise SystemExit("GATEWAY_ACCESS_PASSWORD must have at least 16 characters.")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.state = State()
    print(f"OpenAI API gateway listening at {HOST}:{PORT}, model {MODEL}.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
