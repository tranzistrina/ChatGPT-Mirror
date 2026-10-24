import os

from rest_framework.response import Response
from rest_framework.views import APIView

from app.settings import SHOW_GITHUB, ALLOW_REGISTER


class VersionConfig(APIView):
    authentication_classes = ()
    permission_classes = ()

    def get(self, request):
        # Bypass UI exists only when the explicit localhost-only diagnostic
        # Compose overlay is active. Never advertise it over LAN hostnames.
        hostname = request.get_host().split(":")[0].lower()
        test_mode = (
            os.environ.get("MIRROR_UNSAFE_NO_AUTH_TEST") == "true"
            and hostname in ("127.0.0.1", "localhost")
        )
        return Response({
            "show_github": SHOW_GITHUB,
            "allow_register": ALLOW_REGISTER,
            "no_auth_test": test_mode,
        })
