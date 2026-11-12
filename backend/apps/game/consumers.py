"""WebSocket consumers for Echo verification (Phase 0) and Realtime Rooms (Phase 2+)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.events import PROTOCOL_VERSION, append_event, build_envelope, utc_now_ms
from apps.game.middleware import WSAuthContext
from apps.game.models import RoundPhase
from apps.game.presence import presence_manager
from apps.game.rate_limits import check_typing_rate_limit
from apps.game.state_machine import (
    GameTransitionError,
    build_room_snapshot_payload,
    cast_vote,
    get_active_seat_for_player,
    mark_ready_to_vote,
    play_again,
    send_chat_message,
    start_game,
    submit_answer,
)
from apps.rooms.codes import normalize_room_code
from apps.rooms.models import Player, Room, RoomStatus

WS_CLOSE_AUTH_FAILED = 4401
WS_CLOSE_REPLACED = 4001


def _serialize_lobby_player(player: Player) -> dict[str, Any]:
    """Serialize a human Player for lobby roster/events (never exposes is_bot)."""
    return {
        "id": str(player.id),
        "nickname": player.nickname,
        "is_host": player.is_host,
        "connected": player.connected,
        "score": player.score,
    }


def _compute_can_start(room: Room) -> bool:
    """Return True when room is in LOBBY and enough connected humans are present."""
    if room.status != RoomStatus.LOBBY:
        return False
    connected_humans = room.players.filter(is_bot=False, connected=True).count()
    return connected_humans >= room.min_humans


@database_sync_to_async
def _handle_player_connect(
    room_id: UUID,
    player_id: UUID,
    *,
    was_present: bool,
    present_ids: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Mark player connected, append join/presence Event, and return snapshot + event data."""
    with transaction.atomic():
        room = Room.objects.select_for_update().get(id=room_id)
        player = Player.objects.get(id=player_id, room=room, is_bot=False)
        player.connected = True
        player.last_seen_at = timezone.now()
        player.save(update_fields=["connected", "last_seen_at"])

    can_start = _compute_can_start(room)
    if not was_present:
        event_type = "player_joined"
        event_payload = {
            "player": _serialize_lobby_player(player),
            "can_start": can_start,
        }
    else:
        event_type = "presence"
        event_payload = {
            "player_id": str(player.id),
            "connected": True,
            "can_start": can_start,
        }

    event = append_event(room.id, event_type, event_payload)
    snap_seq, snapshot_payload = build_room_snapshot_payload(
        room.id,
        player.id,
        present_ids=present_ids,
    )
    return (
        {"seq": snap_seq, "payload": snapshot_payload},
        {"seq": event.seq, "type": event_type, "payload": event_payload},
    )


@database_sync_to_async
def _handle_player_disconnect(room_id: UUID, player_id: UUID) -> dict[str, Any] | None:
    """Flag player disconnected immediately and emit presence event."""
    with transaction.atomic():
        room = Room.objects.select_for_update().filter(id=room_id).first()
        if room is None:
            return None
        player = Player.objects.filter(id=player_id, room=room, is_bot=False).first()
        if player is None:
            return None
        player.connected = False
        player.last_seen_at = timezone.now()
        player.save(update_fields=["connected", "last_seen_at"])

    can_start = _compute_can_start(room)
    event_payload = {
        "player_id": str(player.id),
        "connected": False,
        "can_start": can_start,
    }
    event = append_event(room.id, "presence", event_payload)
    return {"seq": event.seq, "type": "presence", "payload": event_payload}


@database_sync_to_async
def _handle_grace_expired(room_id: UUID, player_id: UUID) -> dict[str, Any] | None:
    """Emit player_left if player remains disconnected past 30s grace in LOBBY."""
    with transaction.atomic():
        room = Room.objects.select_for_update().filter(id=room_id).first()
        if room is None or room.status != RoomStatus.LOBBY:
            return None
        player = Player.objects.filter(id=player_id, room=room, is_bot=False).first()
        if player is None or player.connected:
            return None

    can_start = _compute_can_start(room)
    event_payload = {
        "player_id": str(player.id),
        "nickname": player.nickname,
        "reason": "grace_expired",
        "can_start": can_start,
    }
    event = append_event(room.id, "player_left", event_payload)
    return {"seq": event.seq, "type": "player_left", "payload": event_payload}


@database_sync_to_async
def _handle_typing_event(room_id: UUID, player_id: UUID, is_typing: bool) -> str | None:
    """Validate active CHAT seat & typing rate limit; return seat_id string if allowed."""
    if not check_typing_rate_limit(room_id, player_id).allowed:
        return None
    active = get_active_seat_for_player(room_id, player_id)
    if active is None:
        return None
    round_obj, seat = active
    if round_obj.phase != RoundPhase.CHAT:
        return None
    return str(seat.id)


@database_sync_to_async
def _build_unicast_snapshot(room_id: UUID, player_id: UUID) -> tuple[int, dict[str, Any]]:
    return build_room_snapshot_payload(room_id, player_id)


class EchoConsumer(AsyncWebsocketConsumer):
    """Simple Phase 0 echo consumer to verify ASGI + Channels + Vite proxy."""

    async def connect(self) -> None:
        await self.accept()
        await self.send(
            text_data=json.dumps(
                {
                    "v": PROTOCOL_VERSION,
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
                        "v": PROTOCOL_VERSION,
                        "type": "error",
                        "payload": {"code": "invalid_json", "message": "Invalid JSON payload"},
                    }
                )
            )
            return

        await self.send(
            text_data=json.dumps(
                {
                    "v": PROTOCOL_VERSION,
                    "type": "echo",
                    "payload": data,
                }
            )
        )


class RoomConsumer(AsyncWebsocketConsumer):
    """Authenticated multiplayer room WebSocket consumer."""

    room_id: UUID
    room_code: str
    player_id: UUID
    group_name: str
    _authenticated: bool = False

    async def connect(self) -> None:
        auth: WSAuthContext | None = self.scope.get("ws_auth")
        url_code = normalize_room_code(
            str(self.scope.get("url_route", {}).get("kwargs", {}).get("code", ""))
        )
        if auth is None or auth.room_code != url_code:
            await self.close(code=WS_CLOSE_AUTH_FAILED)
            return

        self.room_id = auth.room_id
        self.room_code = auth.room_code
        self.player_id = auth.player_id
        self.group_name = f"room_{self.room_code}"
        self._authenticated = True

        previous_channel = await presence_manager.register_connection(
            self.room_code,
            self.player_id,
            self.channel_name,
        )
        if previous_channel is not None:
            await self.channel_layer.send(previous_channel, {"type": "session.replaced"})

        was_present = await presence_manager.mark_present(self.room_code, self.player_id)
        present_ids = await presence_manager.get_present_ids(self.room_code)
        snapshot, event = await _handle_player_connect(
            self.room_id,
            self.player_id,
            was_present=was_present,
            present_ids=present_ids,
        )

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self.send(
            text_data=json.dumps(
                build_envelope("room_snapshot", snapshot["payload"], seq=snapshot["seq"])
            )
        )
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "room.event",
                "sender_channel": self.channel_name,
                "envelope": build_envelope(
                    event["type"],
                    event["payload"],
                    seq=event["seq"],
                ),
            },
        )

    async def disconnect(self, close_code: int) -> None:
        if not self._authenticated:
            return

        await self.channel_layer.group_discard(self.group_name, self.channel_name)

        is_current = await presence_manager.clear_connection_if_current(
            self.room_code,
            self.player_id,
            self.channel_name,
        )
        if not is_current:
            return

        event = await _handle_player_disconnect(self.room_id, self.player_id)
        if event is not None:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "room.event",
                    "sender_channel": self.channel_name,
                    "envelope": build_envelope(
                        event["type"],
                        event["payload"],
                        seq=event["seq"],
                    ),
                },
            )

        async def _on_grace_expire() -> None:
            left_event = await _handle_grace_expired(self.room_id, self.player_id)
            if left_event is None:
                return
            await presence_manager.clear_present(self.room_code, self.player_id)
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "room.event",
                    "sender_channel": "",
                    "envelope": build_envelope(
                        left_event["type"],
                        left_event["payload"],
                        seq=left_event["seq"],
                    ),
                },
            )

        presence_manager.schedule_grace_timer(self.room_code, self.player_id, _on_grace_expire)

    async def receive(
        self,
        text_data: str | None = None,
        bytes_data: bytes | None = None,
    ) -> None:
        if text_data is None:
            return

        max_bytes = int(getattr(settings, "WS_MAX_PAYLOAD_BYTES", 2048))
        if len(text_data.encode("utf-8")) > max_bytes:
            await self._send_error("payload_too_large", "Message exceeds 2 KB limit.")
            return

        try:
            frame = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error("invalid_json", "Invalid JSON payload.")
            return

        if not isinstance(frame, dict) or frame.get("v") != PROTOCOL_VERSION:
            await self._send_error("invalid_envelope", "Unsupported protocol version or frame.")
            return

        msg_type = frame.get("type")
        raw_payload = frame.get("payload")
        payload = raw_payload if isinstance(raw_payload, dict) else {}

        if msg_type == "ping":
            await self.send(
                text_data=json.dumps(
                    build_envelope("pong", {"server_time": utc_now_ms()}, seq=None)
                )
            )
            return

        if msg_type == "start_game":
            try:
                await database_sync_to_async(start_game)(self.room_id, self.player_id)
            except GameTransitionError as exc:
                await self._send_error(exc.code, exc.message)
            return

        if msg_type == "submit_answer":
            try:
                await database_sync_to_async(submit_answer)(
                    self.room_id,
                    self.player_id,
                    payload.get("text"),
                )
            except GameTransitionError as exc:
                await self._send_error(exc.code, exc.message)
            return

        if msg_type == "send_message":
            try:
                await database_sync_to_async(send_chat_message)(
                    self.room_id,
                    self.player_id,
                    payload.get("text"),
                    client_msg_id=payload.get("client_msg_id"),
                )
            except GameTransitionError as exc:
                await self._send_error(exc.code, exc.message)
            return

        if msg_type == "ready_to_vote":
            try:
                await database_sync_to_async(mark_ready_to_vote)(self.room_id, self.player_id)
            except GameTransitionError as exc:
                await self._send_error(exc.code, exc.message)
            return

        if msg_type == "cast_vote":
            try:
                await database_sync_to_async(cast_vote)(
                    self.room_id,
                    self.player_id,
                    payload.get("target_seat_id"),
                )
            except GameTransitionError as exc:
                await self._send_error(exc.code, exc.message)
            return

        if msg_type == "play_again":
            try:
                await database_sync_to_async(play_again)(self.room_id, self.player_id)
            except GameTransitionError as exc:
                await self._send_error(exc.code, exc.message)
            return

        if msg_type == "typing":
            is_typing = bool(payload.get("is_typing", False))
            seat_id = await _handle_typing_event(self.room_id, self.player_id, is_typing)
            if seat_id is not None:
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "room.event",
                        "sender_channel": self.channel_name,
                        "envelope": build_envelope(
                            "typing",
                            {"seat_id": seat_id, "is_typing": is_typing},
                            seq=None,
                        ),
                    },
                )
            return

        await self._send_error("unknown_type", f"Unsupported message type: {msg_type}")

    async def room_event(self, event: dict[str, Any]) -> None:
        """Forward broadcast room envelope to connected WebSocket clients."""
        if event.get("sender_channel") == self.channel_name:
            return
        await self.send(text_data=json.dumps(event["envelope"]))

    async def room_round_started(self, event: dict[str, Any]) -> None:
        """Send public phase_changed envelope then unicast personalized room_snapshot."""
        await self.send(text_data=json.dumps(event["envelope"]))
        seq, snap_payload = await _build_unicast_snapshot(self.room_id, self.player_id)
        await self.send(
            text_data=json.dumps(build_envelope("room_snapshot", snap_payload, seq=seq))
        )

    async def session_replaced(self, _event: dict[str, Any]) -> None:
        """Close superseded tab cleanly so it does not auto-reconnect in a loop."""
        await self.close(code=WS_CLOSE_REPLACED)

    async def _send_error(self, code: str, message: str) -> None:
        await self.send(
            text_data=json.dumps(
                build_envelope("error", {"code": code, "message": message}, seq=None)
            )
        )
