from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.profile, name="profile"),
    path("password/change/", views.password_change, name="password-change"),
    path("email/", views.mailbox_list, name="mailbox-list"),
    path("email/new/", views.mailbox_create, name="mailbox-create"),
    path("email/<uuid:public_id>/", views.mailbox_update, name="mailbox-update"),
    path("email/<uuid:public_id>/test/", views.mailbox_test, name="mailbox-test"),
]
