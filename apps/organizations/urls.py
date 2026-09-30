from django.urls import path

from .views import employee_create, employee_list, employee_update, organization_settings

app_name = "organizations"

urlpatterns = [
    path("settings/", organization_settings, name="settings"),
    path("employees/", employee_list, name="employees"),
    path("employees/new/", employee_create, name="employee-create"),
    path("employees/<uuid:public_id>/edit/", employee_update, name="employee-update"),
]
