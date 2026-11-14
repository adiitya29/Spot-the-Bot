"""REST API views and server-rendered Open Graph views for viral features."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.html import escape
from django.views import View
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.replays.cards import generate_share_card_png
from apps.replays.models import ReplayCase
from apps.replays.serializers import (
    ReplayCaseDetailSerializer,
    ReplayCaseListSerializer,
    SoloGuessInputSerializer,
)
from apps.replays.services import get_bot_global_stats, record_solo_guess
from apps.rooms.models import Room


class ShareCardView(View):
    """Serve a dynamically generated PNG share card for a completed room."""

    def get(self, request: HttpRequest, code: str) -> HttpResponse:
        normalized_code = code.strip().upper()
        # Strip trailing extension if matched via regex
        if normalized_code.endswith(".PNG"):
            normalized_code = normalized_code[:-4]

        room = Room.objects.filter(code=normalized_code).first()
        if not room:
            raise Http404(f"Room with code '{normalized_code}' not found.")

        png_bytes = generate_share_card_png(room)
        response = HttpResponse(png_bytes, content_type="image/png")
        response["Cache-Control"] = "public, max-age=3600"
        return response


class OpenGraphShareView(View):
    """Server-rendered HTML page with Open Graph & Twitter Cards for social sharing."""

    def get(self, request: HttpRequest, code: str) -> HttpResponse:
        normalized_code = code.strip().upper()
        room = get_object_or_404(Room, code=normalized_code)

        frontend_origin = getattr(settings, "FRONTEND_ORIGIN", "http://localhost:5173").rstrip("/")
        play_url = f"{frontend_origin}/"
        share_img_url = request.build_absolute_uri(f"/api/share/{room.code}.png")
        canonical_url = request.build_absolute_uri(f"/s/{room.code}/")

        title = f"Spot the Bot — Room #{room.code} Match Results"
        description = (
            "One player in the group chat was secretly an AI bot. "
            "Did the humans spot the bot, or did the AI fool everyone? Check the match results!"
        )

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape(title)}</title>

    <!-- Open Graph Metadata -->
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Spot the Bot">
    <meta property="og:title" content="{escape(title)}">
    <meta property="og:description" content="{escape(description)}">
    <meta property="og:image" content="{escape(share_img_url)}">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:url" content="{escape(canonical_url)}">

    <!-- Twitter Card Metadata -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{escape(title)}">
    <meta name="twitter:description" content="{escape(description)}">
    <meta name="twitter:image" content="{escape(share_img_url)}">

    <style>
        body {{
            margin: 0;
            padding: 0;
            background-color: #0b0f19;
            color: #f8fafc;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
        }}
        .container {{
            max-width: 680px;
            margin: 24px;
            padding: 32px;
            background: #151d2f;
            border: 1px solid #334155;
            border-radius: 20px;
            text-align: center;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
        }}
        .badge {{
            display: inline-block;
            background: #1e293b;
            color: #38bdf8;
            font-weight: 700;
            font-size: 14px;
            letter-spacing: 0.05em;
            padding: 6px 14px;
            border-radius: 9999px;
            margin-bottom: 16px;
        }}
        h1 {{
            font-size: 28px;
            margin: 0 0 12px;
            color: #f1f5f9;
        }}
        p {{
            font-size: 16px;
            color: #94a3b8;
            line-height: 1.5;
            margin: 0 0 24px;
        }}
        .card-img {{
            width: 100%;
            border-radius: 12px;
            border: 1px solid #334155;
            margin-bottom: 24px;
            display: block;
        }}
        .btn {{
            display: inline-block;
            background: linear-gradient(135deg, #8b5cf6, #ec4899);
            color: #ffffff;
            font-weight: 700;
            font-size: 16px;
            padding: 14px 28px;
            border-radius: 12px;
            text-decoration: none;
            transition: transform 0.15s ease, opacity 0.15s ease;
        }}
        .btn:hover {{
            opacity: 0.95;
            transform: translateY(-1px);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="badge">SPOT THE BOT</div>
        <h1>Game Results • Room #{escape(room.code)}</h1>
        <p>One player was secretly an AI bot pretending to be human. See how the room voted!</p>
        <img class="card-img" src="{escape(share_img_url)}" alt="Spot the Bot Game Results Card" />
        <div>
            <a class="btn" href="{escape(play_url)}">Play Spot the Bot with Friends</a>
        </div>
    </div>
</body>
</html>"""
        return HttpResponse(html_content, content_type="text/html; charset=utf-8")


class BotStatsView(APIView):
    """GET /api/stats/bot/ - Public aggregate bot deception statistics."""

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        stats = get_bot_global_stats()
        return Response(stats, status=status.HTTP_200_OK)


class ReplayListView(generics.ListAPIView):
    """GET /api/replays/ - List approved, anonymized replay cases for solo play."""

    queryset = ReplayCase.objects.filter(is_approved=True).order_by("-created_at")
    serializer_class = ReplayCaseListSerializer


class ReplayDetailView(generics.RetrieveAPIView):
    """GET /api/replays/<id>/ - Retrieve anonymized round replay transcript for solo play."""

    queryset = ReplayCase.objects.filter(is_approved=True)
    serializer_class = ReplayCaseDetailSerializer


class ReplayGuessView(APIView):
    """POST /api/replays/<id>/guess/ - Submit a solo user's guess identifying the bot."""

    def post(self, request: HttpRequest, pk: str, *args: Any, **kwargs: Any) -> Response:
        replay = get_object_or_404(ReplayCase, id=pk, is_approved=True)

        serializer = SoloGuessInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        guessed_alias = serializer.validated_data["alias"]
        outcome = record_solo_guess(replay.id, guessed_alias)

        return Response(outcome, status=status.HTTP_200_OK)
