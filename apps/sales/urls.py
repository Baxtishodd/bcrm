from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    path("", views.quotation_list, name="list"),
    path("new/", views.quotation_create, name="create"),
    path("orders/", views.order_list, name="order-list"),
    path("orders/<uuid:public_id>/", views.order_detail, name="order-detail"),
    path("orders/<uuid:public_id>/edit/", views.order_update, name="order-update"),
    path("<uuid:public_id>/", views.quotation_detail, name="detail"),
    path("<uuid:public_id>/edit/", views.quotation_update, name="update"),
    path("<uuid:public_id>/print/", views.quotation_print, name="print"),
    path("<uuid:public_id>/convert/", views.quotation_convert, name="convert"),
    path("<uuid:public_id>/lines/new/", views.quotation_line_create, name="line-create"),
    path(
        "<uuid:public_id>/deliveries/new/",
        views.quotation_delivery_create,
        name="delivery-create",
    ),
]
