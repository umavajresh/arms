from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.pages.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("flights/", include("apps.flights.urls")),
    path("bookings/", include("apps.bookings.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("assistant/", include("apps.assistant.urls")),
    path("tracking/", include("apps.tracking.urls")),
    path("manage/", include("apps.console.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
