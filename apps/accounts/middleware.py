from django.contrib import messages
from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

from apps.organizations.models import Membership


class AccountSecurityMiddleware:
    """Enforce active membership and first-login password replacement."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if not user.is_authenticated or user.is_superuser or self._is_exempt(request.path):
            return self.get_response(request)

        has_active_membership = Membership.objects.filter(
            user=user,
            is_active=True,
            organization__is_active=True,
        ).exists()
        if not has_active_membership:
            logout(request)
            if request.path.startswith("/api/"):
                return JsonResponse(
                    {"detail": "Xodim akkaunti bloklangan."},
                    status=403,
                )
            messages.error(request, "Akkauntingiz bloklangan. Administratorga murojaat qiling.")
            return redirect("login")

        if user.must_change_password:
            if request.path.startswith("/api/"):
                return JsonResponse(
                    {"detail": "Davom etishdan oldin parolni almashtiring."},
                    status=403,
                )
            return redirect("accounts:password-change")

        return self.get_response(request)

    @staticmethod
    def _is_exempt(path):
        exempt_paths = {
            reverse("login"),
            reverse("logout"),
            reverse("accounts:password-change"),
            reverse("password-reset"),
            reverse("password-reset-done"),
            reverse("password-reset-complete"),
        }
        return (
            path in exempt_paths
            or path.startswith("/password-reset/")
            or path.startswith("/static/")
            or path.startswith("/media/")
        )
