"""Offline tests: no real tokens, no access to chatgpt.com."""
import base64
import json
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib import error, request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


def fake_jwt(payload):
    data = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return "header." + data + ".signature"


class StreamResponse:
    status_code = 200
    def __init__(self, chunks):
        self.chunks = chunks
        self.closed = False

    def iter_lines(self, decode_unicode=False):
        return iter(self.chunks)

    def close(self):
        self.closed = True


class UnitTests(unittest.TestCase):
    def test_untrusted_jwt_not_used_without_network_validation(self):
        tok = fake_jwt({"email": "person@example.test"})
        fake = mock.Mock(status_code=401)
        with mock.patch.object(server.requests, "get", return_value=fake):
            with self.assertRaises(server.GatewayError):
                server.validate_token(tok)

    def test_upstream_success_and_account_id(self):
        tok = fake_jwt({"email": "person@example.test"}) + "x" * 30
        with mock.patch.object(server.requests, "get", return_value=mock.Mock(status_code=200)) as http:
            info = server.validate_token(tok)
        self.assertEqual(info["user_info"]["email"], "person@example.test")
        self.assertEqual(info["access_token"], tok)
        self.assertEqual(http.call_args.args[0], "https://chatgpt.com/backend-api/models")
        self.assertFalse(http.call_args.kwargs["allow_redirects"])

    def test_session_expiry_and_revoke(self):
        s = server.State()
        key = s.create("alice", "access-secret-that-is-long-enough")
        self.assertIsNotNone(s.get(key))
        s.revoke_user("alice")
        self.assertIsNone(s.get(key))

    def test_sse_current_format(self):
        s = server.Session("alice", "access-secret-that-is-long-enough", 9999999999)
        res = StreamResponse([
            b'data: {"conversation_id":"conv-1","message":{"id":"msg1","author":{"role":"assistant"},"content":{"parts":["Hello"]}}}',
            b'data: [DONE]',
        ])
        with mock.patch.object(server.requests, "post", return_value=res) as upstream:
            events = list(server.stream_conversation(s, "hi", None, None))
        self.assertEqual(events[-1][:3], ("Hello", "conv-1", "msg1"))
        self.assertIn("conv-1", s.conversations)
        self.assertFalse(upstream.call_args.kwargs["allow_redirects"])
        self.assertTrue(res.closed)

    def test_handoff_without_text_does_not_fake_success(self):
        s = server.Session("alice", "access-secret-that-is-long-enough", 9999999999)
        res = StreamResponse([b'data: {"type":"stream_handoff","conversation_id":"conv-1"}', b'data: [DONE]'])
        with mock.patch.object(server.requests, "post", return_value=res):
            with self.assertRaisesRegex(server.GatewayError, "handoff"):
                list(server.stream_conversation(s, "hi", None, None))


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.ADMIN_PASSWORD = "a-password-long-enough-for-tests"
        cls.http = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.http.state = server.State()
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.http.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(timeout=3)

    def post(self, endpoint, data, headers=None):
        h = {"Content-Type": "application/json", **(headers or {})}
        req = request.Request(self.url + endpoint, json.dumps(data).encode(), h, method="POST")
        try:
            with request.urlopen(req, timeout=3) as response:
                return response.status, json.load(response)
        except error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_no_admin_secret_no_gateway_login(self):
        code, _ = self.post("/api/login", {"user_name":"alice", "access_token":"a" * 30})
        self.assertEqual(code, 401)

    def test_admin_password_not_exposed_to_client(self):
        code, result = self.post("/api/login", {
            "user_name": "alice", "access_token": "a" * 30
        }, {"Authorization": "Bearer " + server.ADMIN_PASSWORD})
        self.assertEqual(code, 200)
        token = result["user-gateway-token"]
        self.assertNotEqual(token, server.ADMIN_PASSWORD)
        self.assertIsNotNone(self.http.state.get(token))

    def test_browser_origin_and_no_cookie_required(self):
        code, _ = self.post("/api/chat", {"message": "hi"}, {
            "Origin": "https://attack.example", "Cookie": "user-gateway-token=unknown"})
        self.assertEqual(code, 401)

    def test_csrf_checked_after_valid_session(self):
        key = self.http.state.create("test-csrf", "a" * 30)
        code, result = self.post("/api/chat", {"message": "hi"}, {
            "Origin": "https://attack.example", "Cookie": "user-gateway-token=" + key})
        self.assertEqual(code, 403)
        self.assertIn("origin", result["error"])


if __name__ == "__main__":
    unittest.main()
