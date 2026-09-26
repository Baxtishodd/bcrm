from rest_framework.routers import SimpleRouter

from .api import ProductViewSet

router = SimpleRouter()
router.register("products", ProductViewSet, basename="product")
urlpatterns = router.urls

