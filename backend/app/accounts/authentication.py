from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ActiveUnexpiredTokenAuthentication(TokenAuthentication):
    """Block still-valid DRF tokens for disabled or expired accounts."""

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if not user.is_active:
            raise AuthenticationFailed("Account disabled")
        if user.expired_date and user.expired_date <= timezone.localdate():
            raise AuthenticationFailed("Account expired")
        return user, token
