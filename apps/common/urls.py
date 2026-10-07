from django.urls import path

from .views import dashboard, factory_3d, sales_report

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("factory-3d/", factory_3d, name="factory-3d"),
    path("reports/sales/", sales_report, name="sales-report"),
]
