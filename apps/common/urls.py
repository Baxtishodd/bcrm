from django.urls import path

from .views import dashboard, sales_report

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("reports/sales/", sales_report, name="sales-report"),
]
