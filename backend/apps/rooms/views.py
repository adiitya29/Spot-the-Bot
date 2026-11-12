"""REST API views for room creation, lookup, and guest joining."""

from __future__ import annotations

from django.conf import settings
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.rooms.codes import (
    generate_unique_room_code,
    is_valid_room_code,
    normalize_room_code,
)
from apps.rooms.models import Player, Room, RoomStatus
from apps.rooms.serializers import (
    CreateRoomSerializer,
    JoinRoomSerializer,
    PlayerPublicSerializer,
    RoomPublicSerializer,
    merge_room_config,
)
from apps.rooms.throttles import CreateRoomThrottle, JoinRoomThrottle
from apps.rooms.tokens import sign_player_token


def _error_response(code: str, detail: str, http_status: int) -> Response:
    return Response({"code": code, "detail": detail}, status=http_status)


class RoomCreateView(APIView):
    """POST /api/rooms/ — create a room and return host player + signed token."""

    throttle_classes = [CreateRoomThrottle]

    def post(self, request: Request) -> Response:
        serializer = CreateRoomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        nickname: str = serializer.validated_data["nickname"]
        config = merge_room_config(serializer.validated_data.get("config"))

        for _ in range(5):
            try:
                with transaction.atomic():
                    code = generate_unique_room_code(
                        lambda candidate: Room.objects.filter(code=candidate).exists()
                    )
                    room = Room.objects.create(code=code, config=config)
                    host = Player.objects.create(
                        room=room,
                        nickname=nickname,
                        is_host=True,
                        is_bot=False,
                    )
                    room.host = host
                    room.save(update_fields=["host"])
                break
            except IntegrityError:
                continue
        else:
            return _error_response(
                "code_generation_failed",
                "Could not allocate a unique room code. Please retry.",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        token = sign_player_token(host.id, room.code)
        return Response(
            {
                "code": room.code,
                "room": RoomPublicSerializer(room).data,
                "player": PlayerPublicSerializer(host).data,
                "player_token": token,
            },
            status=status.HTTP_201_CREATED,
        )


class RoomDetailView(APIView):
    """GET /api/rooms/{code}/ — public room status, capacity, and replay setting."""

    def get(self, request: Request, code: str) -> Response:
        normalized = normalize_room_code(code)
        if not is_valid_room_code(normalized):
            return _error_response("room_not_found", "Room not found.", status.HTTP_404_NOT_FOUND)

        room = Room.objects.filter(code=normalized).first()
        if room is None:
            return _error_response("room_not_found", "Room not found.", status.HTTP_404_NOT_FOUND)

        return Response(RoomPublicSerializer(room).data, status=status.HTTP_200_OK)


class RoomJoinView(APIView):
    """POST /api/rooms/{code}/join/ — join an open lobby and receive signed token."""

    throttle_classes = [JoinRoomThrottle]

    def post(self, request: Request, code: str) -> Response:
        normalized = normalize_room_code(code)
        if not is_valid_room_code(normalized):
            return _error_response("room_not_found", "Room not found.", status.HTTP_404_NOT_FOUND)

        serializer = JoinRoomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nickname: str = serializer.validated_data["nickname"]

        max_humans = int(getattr(settings, "MAX_HUMANS_DEFAULT", 7))

        try:
            with transaction.atomic():
                room = Room.objects.select_for_update().filter(code=normalized).first()
                if room is None:
                    return _error_response(
                        "room_not_found",
                        "Room not found.",
                        status.HTTP_404_NOT_FOUND,
                    )

                if room.status == RoomStatus.IN_PROGRESS:
                    return _error_response(
                        "room_started",
                        "This game has already started.",
                        status.HTTP_409_CONFLICT,
                    )
                if room.status != RoomStatus.LOBBY:
                    return _error_response(
                        "room_closed",
                        "This room is no longer accepting players.",
                        status.HTTP_409_CONFLICT,
                    )

                human_count = room.players.filter(is_bot=False).count()
                if human_count >= max_humans:
                    return _error_response(
                        "room_full",
                        "This room is full.",
                        status.HTTP_409_CONFLICT,
                    )

                if room.players.filter(nickname__iexact=nickname).exists():
                    return _error_response(
                        "nickname_taken",
                        "That nickname is already taken in this room.",
                        status.HTTP_409_CONFLICT,
                    )

                player = Player.objects.create(
                    room=room,
                    nickname=nickname,
                    is_host=False,
                    is_bot=False,
                )
        except IntegrityError:
            return _error_response(
                "nickname_taken",
                "That nickname is already taken in this room.",
                status.HTTP_409_CONFLICT,
            )

        token = sign_player_token(player.id, room.code)
        return Response(
            {
                "room": RoomPublicSerializer(room).data,
                "player": PlayerPublicSerializer(player).data,
                "player_token": token,
            },
            status=status.HTTP_200_OK,
        )
