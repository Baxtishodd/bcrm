from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    path("", views.quotation_list, name="list"),
    path("new/", views.quotation_create, name="create"),
    path(
        "new/from-lead/<uuid:lead_public_id>/",
        views.quotation_create,
        name="create-from-lead",
    ),
    path("orders/", views.order_list, name="order-list"),
    path("orders/<uuid:public_id>/", views.order_detail, name="order-detail"),
    path("orders/<uuid:public_id>/edit/", views.order_update, name="order-update"),
    path(
        "orders/<uuid:public_id>/payment-plans/new/",
        views.payment_plan_create,
        name="payment-plan-create",
    ),
    path(
        "orders/<uuid:public_id>/payments/new/",
        views.payment_create,
        name="payment-create",
    ),
    path(
        "payment-plans/<uuid:public_id>/edit/",
        views.payment_plan_update,
        name="payment-plan-update",
    ),
    path(
        "payment-plans/<uuid:public_id>/cancel/",
        views.payment_plan_cancel,
        name="payment-plan-cancel",
    ),
    path(
        "payments/<uuid:public_id>/edit/",
        views.payment_update,
        name="payment-update",
    ),
    path(
        "payments/<uuid:public_id>/cancel/",
        views.payment_cancel,
        name="payment-cancel",
    ),
    path("<uuid:public_id>/", views.quotation_detail, name="detail"),
    path("<uuid:public_id>/edit/", views.quotation_update, name="update"),
    path(
        "<uuid:public_id>/document/",
        views.quotation_document_edit,
        name="document-edit",
    ),
    path("<uuid:public_id>/pdf/", views.quotation_pdf, name="pdf"),
    path("<uuid:public_id>/print/", views.quotation_print, name="print"),
    path("<uuid:public_id>/email/", views.quotation_email_send, name="email-send"),
    path("<uuid:public_id>/convert/", views.quotation_convert, name="convert"),
    path("<uuid:public_id>/lines/new/", views.quotation_line_create, name="line-create"),
    path(
        "<uuid:public_id>/deliveries/new/",
        views.quotation_delivery_create,
        name="delivery-create",
    ),
]
