from .permissions import permissions_for_membership
from .tenancy import get_membership


class OrganizationContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        membership = get_membership(request.user)
        request.membership = membership
        request.organization = membership.organization if membership else None
        request.crm_permissions = permissions_for_membership(
            membership,
            is_superuser=request.user.is_authenticated and request.user.is_superuser,
        )
        return self.get_response(request)
