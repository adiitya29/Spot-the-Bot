"""Phase 0 baseline tests covering health HTTP endpoint, EchoConsumer, and scheduler."""

from __future__ import annotations

import json

import pytest
from channels.testing import WebsocketCommunicator
from django.core.management import call_command
from django.test import Client

from config.asgi import application
from config.celery import app as celery_app


def test_celery_app_configured() -> None:
    """Celery application initializes cleanly with expected name."""
    assert celery_app.main == "spot_the_bot"


def test_health_endpoint() -> None:
    """GET /api/health/ returns 200 with ok payload."""
    client = Client()
    response = client.get("/api/health/")
    assert response.status_code == 200
    assert json.loads(response.content) == {"status": "ok"}


@pytest.mark.asyncio
async def test_echo_websocket_consumer() -> None:
    """EchoConsumer accepts valid-origin connection, echoes JSON, and flags bad JSON."""
    communicator = WebsocketCommunicator(
        application,
        "/ws/echo/",
        headers=[(b"origin", b"http://localhost:5173")],
    )
    connected, _ = await communicator.connect()
    assert connected

    greeting = await communicator.receive_json_from()
    assert greeting == {
        "v": 1,
        "type": "connected",
        "payload": {"message": "echo ready"},
    }

    await communicator.send_json_to({"msg": "hello bot"})
    echoed = await communicator.receive_json_from()
    assert echoed == {
        "v": 1,
        "type": "echo",
        "payload": {"msg": "hello bot"},
    }

    await communicator.send_to(text_data="not-valid-json")
    error_msg = await communicator.receive_json_from()
    assert error_msg["type"] == "error"
    assert error_msg["payload"]["code"] == "invalid_json"

    await communicator.disconnect()


@pytest.mark.asyncio
async def test_echo_websocket_rejects_disallowed_origin() -> None:
    """Origin validator rejects WebSocket connections from unknown origins."""
    communicator = WebsocketCommunicator(
        application,
        "/ws/echo/",
        headers=[(b"origin", b"http://evil.example")],
    )
    connected, _ = await communicator.connect()
    assert not connected


def test_run_scheduler_once_exits_cleanly() -> None:
    """Placeholder scheduler --once runs one tick without error."""
    call_command("run_scheduler", "--once")
