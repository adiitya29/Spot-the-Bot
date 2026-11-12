"""WebSocket URL routing."""

from __future__ import annotations

from django.urls import path

from apps.game.consumers import EchoConsumer

websocket_urlpatterns = [
    path("ws/echo/", EchoConsumer.as_asgi()),
]
