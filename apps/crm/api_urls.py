from rest_framework.routers import SimpleRouter

from .api import LeadViewSet

router = SimpleRouter()
router.register("leads", LeadViewSet, basename="lead")
urlpatterns = router.urls

