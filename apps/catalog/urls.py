from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.product_list, name="list"),
    path("prices/", views.price_list, name="price-list"),
    path("offers/", views.offer_list, name="offer-list"),
    path("offers/new/", views.offer_create, name="offer-create"),
    path("offers/<uuid:public_id>/", views.offer_detail, name="offer-detail"),
    path(
        "offers/<uuid:public_id>/edit/",
        views.offer_update,
        name="offer-update",
    ),
    path(
        "offers/<uuid:public_id>/new-version/",
        views.offer_create_version,
        name="offer-create-version",
    ),
    path(
        "offers/<uuid:public_id>/document/",
        views.offer_document_edit,
        name="offer-document-edit",
    ),
    path(
        "offers/<uuid:public_id>/pdf/",
        views.offer_pdf,
        name="offer-pdf",
    ),
    path(
        "offers/<uuid:public_id>/lines/new/",
        views.offer_line_create,
        name="offer-line-create",
    ),
    path("new/", views.product_create, name="create"),
    path("<uuid:public_id>/", views.product_detail, name="detail"),
    path("<uuid:public_id>/edit/", views.product_update, name="update"),
    path(
        "<uuid:public_id>/specification/",
        views.product_specification_update,
        name="specification-update",
    ),
    path("<uuid:public_id>/variants/new/", views.variant_create, name="variant-create"),
]
