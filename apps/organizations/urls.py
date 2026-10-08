from django.urls import path

from .views import (
    employee_create,
    employee_list,
    employee_update,
    organization_settings,
    role_create,
    role_delete,
    role_list,
    role_update,
)

app_name = "organizations"

urlpatterns = [
    path("settings/", organization_settings, name="settings"),
    path("employees/", employee_list, name="employees"),
    path("employees/new/", employee_create, name="employee-create"),
    path("employees/<uuid:public_id>/edit/", employee_update, name="employee-update"),
    path("roles/", role_list, name="roles"),
    path("roles/new/", role_create, name="role-create"),
    path("roles/<uuid:public_id>/edit/", role_update, name="role-update"),
    path("roles/<uuid:public_id>/delete/", role_delete, name="role-delete"),
]
