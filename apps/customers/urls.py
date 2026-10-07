from django.urls import path

from . import views

app_name = "customers"

urlpatterns = [
    path("", views.customer_list, name="list"),
    path("new/", views.customer_create, name="create"),
    path("contacts/", views.contact_list, name="contact-list"),
    path("contacts/new/", views.contact_create, name="contact-create"),
    path("contacts/<uuid:public_id>/", views.contact_detail, name="contact-detail"),
    path("contacts/<uuid:public_id>/edit/", views.contact_update, name="contact-update"),
    path("<uuid:public_id>/", views.customer_detail, name="detail"),
    path("<uuid:public_id>/edit/", views.customer_update, name="update"),
    path(
        "<uuid:customer_public_id>/contacts/new/",
        views.contact_create,
        name="customer-contact-create",
    ),
]
