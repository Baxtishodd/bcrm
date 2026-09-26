from rest_framework.routers import SimpleRouter

from .api import CustomerCompanyViewSet

router = SimpleRouter()
router.register("companies", CustomerCompanyViewSet, basename="customer-company")
urlpatterns = router.urls

