from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, reverse_lazy
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.accounts.views import AccountPasswordResetConfirmView

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
            success_url=reverse_lazy("password-reset-done"),
        ),
        name="password-reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password-reset-done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        AccountPasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password-reset-complete",
    ),
    path("api/v1/", include("config.api_urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
    path("customers/", include("apps.customers.urls")),
    path("leads/", include("apps.crm.urls")),
    path("tasks/", include("apps.crm.task_urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("sales/", include("apps.sales.urls")),
    path("organization/", include("apps.organizations.urls")),
    path("account/", include("apps.accounts.urls")),
    path("", include("apps.common.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
