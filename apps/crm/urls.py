from django.urls import path

from . import views

app_name = "crm"

urlpatterns = [
    path("", views.lead_list, name="list"),
    path("new/", views.lead_create, name="create"),
    path("<uuid:public_id>/", views.lead_detail, name="detail"),
    path("<uuid:public_id>/edit/", views.lead_update, name="update"),
    path("<uuid:public_id>/status/", views.lead_status_update, name="status-update"),
    path("<uuid:public_id>/activities/new/", views.activity_create, name="activity-create"),
]
