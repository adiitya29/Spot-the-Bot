"""ASGI application routing HTTP and WebSocket traffic."""

from __future__ import annotations

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

django_asgi_app = get_asgi_application()

from apps.game.middleware import DynamicOriginValidator, TokenAuthMiddleware  # noqa: E402
from apps.game.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": DynamicOriginValidator(
            TokenAuthMiddleware(URLRouter(websocket_urlpatterns)),
        ),
    }
)
