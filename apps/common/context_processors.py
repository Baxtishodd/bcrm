from django.db.models import Sum


def organization_context(request):
    organization = getattr(request, "organization", None)
    team_unread_count = 0
    if organization and request.user.is_authenticated:
        from apps.communications.models import ConversationParticipant

        team_unread_count = (
            ConversationParticipant.objects.filter(
                organization=organization,
                user=request.user,
            ).aggregate(total=Sum("unread_count"))["total"]
            or 0
        )
    return {
        "organization": organization,
        "crm_membership": getattr(request, "membership", None),
        "crm_permissions": getattr(request, "crm_permissions", {}),
        "team_unread_count": team_unread_count,
    }
