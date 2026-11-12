"""URL routes for room creation, inspection, and joining."""

from __future__ import annotations

from django.urls import URLPattern, path

from apps.rooms.views import RoomCreateView, RoomDetailView, RoomJoinView

urlpatterns: list[URLPattern] = [
    path("", RoomCreateView.as_view(), name="room-create"),
    path("<str:code>/", RoomDetailView.as_view(), name="room-detail"),
    path("<str:code>/join/", RoomJoinView.as_view(), name="room-join"),
]
