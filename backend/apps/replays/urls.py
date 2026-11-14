"""URL configuration for replays, bot statistics, and share assets."""

from __future__ import annotations

from django.urls import path, re_path

from apps.replays.views import (
    BotStatsView,
    ReplayDetailView,
    ReplayGuessView,
    ReplayListView,
    ShareCardView,
)

app_name = "replays"

urlpatterns = [
    re_path(r"^share/(?P<code>[A-Za-z0-9]+)\.png$", ShareCardView.as_view(), name="share-card-png"),
    path("share/<str:code>.png", ShareCardView.as_view(), name="share-card-png-direct"),
    path("stats/bot/", BotStatsView.as_view(), name="bot-stats"),
    path("replays/", ReplayListView.as_view(), name="replay-list"),
    path("replays/<uuid:pk>/", ReplayDetailView.as_view(), name="replay-detail"),
    path("replays/<uuid:pk>/guess/", ReplayGuessView.as_view(), name="replay-guess"),
]
