from django.urls import path

from .views import organization_settings

app_name = "organizations"

urlpatterns = [path("settings/", organization_settings, name="settings")]
