def organization_context(request):
    return {
        "organization": getattr(request, "organization", None),
        "crm_membership": getattr(request, "membership", None),
        "crm_permissions": getattr(request, "crm_permissions", {}),
    }
