"""WebSocket consumers (Phase 0 EchoConsumer; RoomConsumer added in Phase 2)."""

from __future__ import annotations

import json
from typing import Any

from channels.generic.websocket import AsyncWebsocketConsumer


class EchoConsumer(AsyncWebsocketConsumer):
    """Simple Phase 0 echo consumer to verify ASGI + Channels + Vite proxy."""

    async def connect(self) -> None:
        await self.accept()
        await self.send(
            text_data=json.dumps(
                {
                    "v": 1,
                    "type": "connected",
                    "payload": {"message": "echo ready"},
                }
            )
        )

    async def receive(
        self,
        text_data: str | None = None,
        bytes_data: bytes | None = None,
    ) -> None:
        if text_data is None:
            return
        try:
            data: Any = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps(
                    {
                        "v": 1,
                        "type": "error",
                        "payload": {"code": "invalid_json", "message": "Invalid JSON payload"},
                    }
                )
            )
            return

        await self.send(
            text_data=json.dumps(
                {
                    "v": 1,
                    "type": "echo",
                    "payload": data,
                }
            )
        )
