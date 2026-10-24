from unittest.mock import patch
from datetime import timedelta
from django.utils import timezone
from rest_framework.authtoken.models import Token

from django.test import TestCase
from rest_framework.test import APIClient

from app.accounts.models import User
from app.chatgpt.models import ChatgptAccount


class AuthorizationRegressionTests(TestCase):
    def test_no_pools_gives_no_accounts(self):
        ChatgptAccount.objects.create(
            chatgpt_username="test@example.invalid",
            plan_type="plus",
            access_token="test-value",
            created_time=0,
            updated_time=0,
        )
        self.assertEqual(ChatgptAccount.get_by_gptcar_list([]).count(), 0)

    def test_unauthorized_token_lookup(self):
        owner = User.objects.create_user("owner", password="testing123")
        other = User.objects.create_user("other", password="testing456")
        client = APIClient()
        client.force_authenticate(user=owner)
        with patch("app.accounts.views.req_gateway") as gateway:
            response = client.get("/0x/user/get-mirror-token", {"user_id": other.pk})
        self.assertEqual(response.status_code, 403)
        gateway.assert_not_called()

    def test_expired_account_cannot_reuse_token(self):
        user = User.objects.create_user("expired", password="testing789")
        user.expired_date = timezone.localdate() - timedelta(days=1)
        user.save()
        client = APIClient()
        token = Token.objects.create(user=user)
        client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        response = client.get("/0x/user/chatgpt-list")
        self.assertEqual(response.status_code, 401)

    def test_disabled_account_cannot_reuse_token(self):
        user = User.objects.create_user("disabled", password="testing789")
        user.is_active = False
        user.save()
        client = APIClient()
        token = Token.objects.create(user=user)
        client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        response = client.get("/0x/user/chatgpt-list")
        self.assertEqual(response.status_code, 401)


class PasswordlessDiagnosticTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("admin", password="unrelated-secret")
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()

    def test_disabled_by_default_even_on_localhost(self):
        with patch.dict("os.environ", {"MIRROR_UNSAFE_NO_AUTH_TEST": "false", "ADMIN_USERNAME": "admin"}):
            response = APIClient().post(
                "/0x/user/no-auth-test-login", {},
                format="json", HTTP_HOST="127.0.0.1:50002",
            )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Token.objects.filter(user=self.user).exists())

    def test_enabled_only_on_localhost(self):
        with patch.dict("os.environ", {"MIRROR_UNSAFE_NO_AUTH_TEST": "true", "ADMIN_USERNAME": "admin"}):
            remote = APIClient().post(
                "/0x/user/no-auth-test-login", {},
                format="json", HTTP_HOST="testserver",
            )
            self.assertEqual(remote.status_code, 403)
            response = APIClient().post(
                "/0x/user/no-auth-test-login", {},
                format="json", HTTP_HOST="127.0.0.1:50002",
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_admin"])
        self.assertTrue(response.json()["test_only"])
        issued = response.json()["admin_token"]
        probe = User.objects.get(username="__mirror_noauth_probe__")
        self.assertFalse(probe.has_usable_password())
        self.assertTrue(probe.is_staff)
        self.assertTrue(Token.objects.filter(user=probe, key=issued).exists())
        self.assertFalse(Token.objects.filter(user=self.user).exists())
        self.assertTrue(self.user.check_password("unrelated-secret"))
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token " + issued)
        protected = client.get("/0x/user/chatgpt-list")
        self.assertEqual(protected.status_code, 200)

    def test_reserved_diagnostic_account_with_bad_role_denied(self):
        reserved = User.objects.create_user("__mirror_noauth_probe__", password=None)
        reserved.is_staff = False
        reserved.save()
        with patch.dict("os.environ", {"MIRROR_UNSAFE_NO_AUTH_TEST": "true", "ADMIN_USERNAME": "admin"}):
            response = APIClient().post(
                "/0x/user/no-auth-test-login", {},
                format="json", HTTP_HOST="127.0.0.1:50002",
            )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Token.objects.filter(user=reserved).exists())

    def test_config_only_advertises_bypass_on_localhost(self):
        with patch.dict("os.environ", {"MIRROR_UNSAFE_NO_AUTH_TEST": "true", "ADMIN_USERNAME": "admin"}):
            local = APIClient().get("/0x/user/version-cfg", HTTP_HOST="127.0.0.1:50002")
            remote = APIClient().get("/0x/user/version-cfg", HTTP_HOST="testserver")
        self.assertTrue(local.json()["no_auth_test"])
        self.assertFalse(remote.json()["no_auth_test"])


class OrdinaryUserFlowTests(TestCase):
    def test_admin_can_assign_pool_and_regular_user_can_select_chatgpt(self):
        from app.chatgpt.models import ChatgptCar

        admin = User.objects.create_superuser("admin", password="temporary-test-only")
        chatgpt = ChatgptAccount.objects.create(
            chatgpt_username="assigned@example.invalid",
            plan_type="plus",
            access_token="synthetic-test-token-not-sent-to-OpenAI",
            created_time=0, updated_time=0,
        )
        pool = ChatgptCar.objects.create(
            car_name="local_test_pool",
            gpt_account_list=[chatgpt.pk],
            created_time=0, updated_time=0,
        )
        admin_client = APIClient()
        admin_client.force_authenticate(user=admin)
        result = admin_client.post("/0x/user/", {
            "username": "demo_user",
            "password": "demo_user_password",
            "is_active": True,
            "gptcar_list": [pool.pk],
            "model_limit": [],
            "isolated_session": True,
            "remark": "test only",
            "expired_date": None,
        }, format="json")
        self.assertEqual(result.status_code, 200, result.content)

        client = APIClient(HTTP_USER_AGENT="MirrorIntegrationTest/1")
        login = client.post("/0x/user/login", {
            "username": "demo_user", "password": "demo_user_password"
        }, format="json")
        self.assertEqual(login.status_code, 200, login.content)
        self.assertFalse(login.json().get("is_admin", False))
        client.credentials(HTTP_AUTHORIZATION="Token " + login.json()["admin_token"])

        with patch("app.accounts.views.req_gateway", return_value={}):
            available = client.get("/0x/user/chatgpt-list")
        self.assertEqual(available.status_code, 200, available.content)
        self.assertEqual(len(available.json()["results"]), 1)
        self.assertEqual(available.json()["results"][0]["id"], chatgpt.pk)

        with patch("app.chatgpt.views.chatgpt.req_gateway",
                   return_value={"user-gateway-token": "diagnostic-placeholder"}):
            selected = client.post("/0x/chatgpt/login", {
                "chatgpt_id": chatgpt.pk
            }, format="json")
        self.assertEqual(selected.status_code, 200, selected.content)
        self.assertEqual(
            selected.json()["user-gateway-token"], "diagnostic-placeholder"
        )
