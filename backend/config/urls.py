"""Root URL configuration."""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from apps.common.views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health-check"),
    path("api/rooms/", include("apps.rooms.urls")),
    path("api/", include("apps.replays.urls")),
]
