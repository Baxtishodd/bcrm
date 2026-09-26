from rest_framework.routers import DefaultRouter

from .api import QuotationViewSet, SalesOrderViewSet

router = DefaultRouter()
router.register("quotations", QuotationViewSet, basename="quotation")
router.register("orders", SalesOrderViewSet, basename="order")

urlpatterns = router.urls
