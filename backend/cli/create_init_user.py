import os
import sys

import django

cur_path = os.path.abspath(__file__)
parent = os.path.dirname
sys.path.append(parent(parent(cur_path)))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

if __name__ == "__main__":
    from app.accounts.models import User
    from app.settings import FREE_ACCOUNT_USERNAME, ADMIN_USERNAME, ADMIN_PASSWORD

    # Always revoke the disposable diagnostic admin and its DRF token on a
    # normal restart. The normal LAN service must never inherit test access.
    if os.environ.get("MIRROR_UNSAFE_NO_AUTH_TEST") != "true":
        User.objects.filter(username="__mirror_noauth_probe__").delete()

    test_admin = os.environ.get("MIRROR_UNSAFE_ADMIN_TEST_LOGIN") == "true"
    if test_admin and ADMIN_USERNAME != "admin":
        raise RuntimeError("Test login requires ADMIN_USERNAME=admin")
    if not ADMIN_USERNAME:
        raise RuntimeError("ADMIN_USERNAME must be configured")

    # Fixed admin / 12345 is ONLY enabled by the explicit test-only
    # Compose overlay. Keep the normal strong gateway ADMIN_PASSWORD intact.
    local_password = "12345" if test_admin else ADMIN_PASSWORD
    if not local_password:
        raise RuntimeError("ADMIN_PASSWORD must be configured")

    defaults = {"remark": "超级管理员", "isolated_session": False}
    user, created = User.objects.get_or_create(username=ADMIN_USERNAME, defaults=defaults)
    user.set_password(local_password)
    # Ensure a previous expired local-admin account cannot block test login.
    if test_admin:
        user.expired_date = None
    user.is_staff = True
    user.is_active = True
    user.is_superuser = True

    user.save()
    print("Superuser created.")
    if test_admin:
        print("INSECURE TEST LOGIN ENABLED: admin / 12345 (LAN exposed; disable after debugging)")

    defaults = {
        "remark": "用于免费体验",
        "is_active": False,
        "isolated_session": True,
        "model_limit": [
            {"every_minute": 1, "limit_count": 3, "model_name": "gpt-4"},
            {"every_minute": 1, "limit_count": 3, "model_name": "gpt-4o"},
            {"every_minute": 1, "limit_count": 3, "model_name": "gpt-4o-mini"},
            {"every_minute": 1, "limit_count": 1, "model_name": "o1-mini"},
            {"every_minute": 1, "limit_count": 1, "model_name": "o1", },
            {"every_minute": 1, "limit_count": 1, "model_name": "o1-pro", }

        ]
    }
    user, created = User.objects.get_or_create(username=FREE_ACCOUNT_USERNAME, defaults=defaults)
    user.is_superuser = False
    user.save()
    print("Freeuser created.")
