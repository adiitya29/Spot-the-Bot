"""Shared health check endpoint."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse


def health_check(request: HttpRequest) -> JsonResponse:
    """Return service liveness status."""
    return JsonResponse({"status": "ok"})
