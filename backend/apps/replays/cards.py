"""Dynamic Pillow share card generation for game outcomes and social previews."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

from apps.game.models import RoundResult
from apps.rooms.models import Player, Room

CARD_WIDTH = 1200
CARD_HEIGHT = 630


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """Load default FreeType font scaled to requested pixel size."""
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()  # type: ignore[return-value]


def generate_share_card_png(room: Room) -> bytes:
    """Generate high-resolution (1200x630) social share card PNG for a completed room game."""
    img = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), color=(11, 15, 25, 255))
    draw = ImageDraw.Draw(img)

    # 1. Background styling: Inner card container with modern border
    card_margin = 36
    card_box = (
        card_margin,
        card_margin,
        CARD_WIDTH - card_margin,
        CARD_HEIGHT - card_margin,
    )
    draw.rounded_rectangle(
        card_box,
        radius=24,
        fill=(21, 29, 47, 255),
        outline=(51, 65, 85, 255),
        width=3,
    )

    # Decorative top glow accent line
    draw.rounded_rectangle(
        (card_margin + 20, card_margin, CARD_WIDTH - card_margin - 20, card_margin + 6),
        radius=3,
        fill=(139, 92, 246, 255),
    )

    # 2. Header: Logo pill and Room Code badge
    font_badge = _get_font(20)
    font_room = _get_font(22)

    # Brand pill: [ 🤖 SPOT THE BOT ]
    draw.rounded_rectangle((70, 68, 300, 108), radius=12, fill=(30, 41, 59, 255))
    draw.text((86, 78), "SPOT THE BOT", font=font_badge, fill=(56, 189, 248, 255))

    # Room code pill on top right
    code_text = f"ROOM #{room.code}"
    draw.rounded_rectangle(
        (CARD_WIDTH - 280, 68, CARD_WIDTH - 70, 108),
        radius=12,
        fill=(30, 41, 59, 255),
        outline=(71, 85, 105, 255),
        width=1,
    )
    draw.text((CARD_WIDTH - 250, 77), code_text, font=font_room, fill=(241, 245, 249, 255))

    # 3. Game Outcome & Headline
    results = list(
        RoundResult.objects.filter(round__room=room)
        .select_related("round__topic")
        .order_by("round__number")
    )
    total_rounds = len(results)
    bot_fooled_count = sum(1 for r in results if r.bot_fooled)
    bot_won = bot_fooled_count > (total_rounds / 2) if total_rounds > 0 else False

    font_headline = _get_font(46)
    font_subtitle = _get_font(24)

    if bot_won:
        headline = "THE AI BOT FOOLED THE ROOM!"
        headline_color = (167, 139, 250, 255)  # Purple-400
        subtitle = (
            f"The covert AI escaped detection in {bot_fooled_count} of {total_rounds} rounds."
            if total_rounds > 0
            else "The AI player blended in completely."
        )
    else:
        headline = "HUMANS SPOTTED THE AI BOT!"
        headline_color = (52, 211, 153, 255)  # Emerald-400
        uncovered = total_rounds - bot_fooled_count
        subtitle = (
            f"Humans accurately uncovered the covert AI in {uncovered} of {total_rounds} rounds."
            if total_rounds > 0
            else "The humans identified the robot in chat!"
        )

    draw.text((70, 150), headline, font=font_headline, fill=headline_color)
    draw.text((72, 212), subtitle, font=font_subtitle, fill=(148, 163, 184, 255))

    # 4. Divider line
    draw.line((70, 260, CARD_WIDTH - 70, 260), fill=(51, 65, 85, 255), width=2)

    # 5. Leaderboard / Top Participants Section
    font_section = _get_font(20)
    font_player_rank = _get_font(22)
    font_player_name = _get_font(22)
    font_player_score = _get_font(20)

    draw.text((70, 280), "FINAL SCORES", font=font_section, fill=(100, 116, 139, 255))

    top_players = list(
        Player.objects.filter(room=room).exclude(is_bot=True).order_by("-score", "nickname")[:4]
    )

    medal_icons = ["1st", "2nd", "3rd", "4th"]
    medal_colors = [
        (251, 191, 36, 255),  # Gold
        (203, 213, 225, 255),  # Silver
        (217, 119, 6, 255),  # Bronze
        (148, 163, 184, 255),  # Slate
    ]

    card_y = 320
    for idx, player in enumerate(top_players):
        # Position 4 player slots horizontally
        box_width = 240
        box_x = 70 + (idx * (box_width + 25))

        draw.rounded_rectangle(
            (box_x, card_y, box_x + box_width, card_y + 160),
            radius=16,
            fill=(30, 41, 59, 255),
            outline=(51, 65, 85, 255),
            width=2,
        )

        rank_str = medal_icons[idx] if idx < len(medal_icons) else f"{idx + 1}th"
        m_color = medal_colors[idx] if idx < len(medal_colors) else (148, 163, 184, 255)
        draw.text((box_x + 16, card_y + 18), rank_str, font=font_player_rank, fill=m_color)

        nick = player.nickname[:14]
        draw.text((box_x + 16, card_y + 60), nick, font=font_player_name, fill=(248, 250, 252, 255))

        score_text = f"{player.score} pts"
        draw.text(
            (box_x + 16, card_y + 105),
            score_text,
            font=font_player_score,
            fill=(56, 189, 248, 255),
        )

    # 6. Footer call to action
    font_footer = _get_font(20)
    footer_text = "Can you spot the AI among humans? Play free at Spot The Bot"
    footer_y = CARD_HEIGHT - card_margin - 34
    draw.text((70, footer_y), footer_text, font=font_footer, fill=(100, 116, 139, 255))

    # Output as PNG bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
