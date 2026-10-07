from django.urls import path

from . import views

app_name = "communications"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("sync/", views.inbox_sync, name="sync"),
    path("new/", views.conversation_create, name="create"),
    path("email/new/", views.email_compose, name="email-compose"),
    path("telegram/webhook/", views.telegram_webhook, name="telegram-webhook"),
    path("<uuid:public_id>/", views.inbox, name="conversation"),
    path("<uuid:public_id>/send/", views.message_create, name="send"),
]
