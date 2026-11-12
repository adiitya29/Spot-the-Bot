"""WebSocket URL routing."""

from __future__ import annotations

from django.urls import path, re_path

from apps.game.consumers import EchoConsumer, RoomConsumer

websocket_urlpatterns = [
    path("ws/echo/", EchoConsumer.as_asgi()),
    re_path(r"^ws/rooms/(?P<code>[A-Za-z0-9]+)/?$", RoomConsumer.as_asgi()),
]
