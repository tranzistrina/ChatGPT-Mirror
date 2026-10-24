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
