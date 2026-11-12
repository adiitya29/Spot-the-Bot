"""Factory Boy factories for Room and Player models."""

from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from apps.rooms.codes import generate_room_code
from apps.rooms.models import Player, Room, default_room_config


class RoomFactory(DjangoModelFactory):
    """Factory creating Room instances with unique 6-character codes."""

    class Meta:
        model = Room

    code = factory.LazyFunction(generate_room_code)
    config = factory.LazyFunction(default_room_config)


class PlayerFactory(DjangoModelFactory):
    """Factory creating guest Player instances inside a Room."""

    class Meta:
        model = Player

    room = factory.SubFactory(RoomFactory)
    nickname = factory.Sequence(lambda n: f"Player{n}")
    is_bot = False
    is_host = False
