from django.urls import path

from . import views

app_name = "communications"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("sync/", views.inbox_sync, name="sync"),
    path("team/", views.team_inbox, name="team-inbox"),
    path("team/sync/", views.team_inbox_sync, name="team-sync"),
    path(
        "team/start/<uuid:membership_id>/",
        views.start_internal_conversation,
        name="team-start",
    ),
    path("team/<uuid:public_id>/", views.team_inbox, name="team-conversation"),
    path("new/", views.conversation_create, name="create"),
    path("email/new/", views.email_compose, name="email-compose"),
    path("telegram/webhook/", views.telegram_webhook, name="telegram-webhook"),
    path("<uuid:public_id>/", views.inbox, name="conversation"),
    path("<uuid:public_id>/send/", views.message_create, name="send"),
]
