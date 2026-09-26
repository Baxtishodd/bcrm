from django.urls import path

from . import views

app_name = "customers"

urlpatterns = [
    path("", views.customer_list, name="list"),
    path("new/", views.customer_create, name="create"),
    path("<uuid:public_id>/", views.customer_detail, name="detail"),
    path("<uuid:public_id>/edit/", views.customer_update, name="update"),
    path("<uuid:public_id>/contacts/new/", views.contact_create, name="contact-create"),
]

