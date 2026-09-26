from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.product_list, name="list"),
    path("new/", views.product_create, name="create"),
    path("<uuid:public_id>/", views.product_detail, name="detail"),
    path("<uuid:public_id>/edit/", views.product_update, name="update"),
    path("<uuid:public_id>/variants/new/", views.variant_create, name="variant-create"),
]

