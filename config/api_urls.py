from django.urls import include, path

urlpatterns = [
    path("customers/", include("apps.customers.api_urls")),
    path("crm/", include("apps.crm.api_urls")),
    path("catalog/", include("apps.catalog.api_urls")),
    path("sales/", include("apps.sales.api_urls")),
]
