"""Seed the 40 default party topics idempotently.

Run inside backend directory: python scripts/seed_topics.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TOPIC_SEEDS: tuple[tuple[str, str], ...] = (
    # funny (14)
    ("funny", "What is the pettiest reason you ever stopped talking to someone?"),
    ("funny", "What completely useless skill could you genuinely win a medal in?"),
    ("funny", "What food combination do you swear by that grosses everyone else out?"),
    ("funny", "What is the weirdest thing you have ever seen inside a public bathroom or train?"),
    ("funny", "What lie did an adult tell you as a kid that you believed way too long?"),
    ("funny", "If animals could leave online reviews about humans, what would squirrels write?"),
    ("funny", "What is the worst haircut or fashion phase you defended in real time?"),
    ("funny", "What household chore feels personally insulting to do twice in one week?"),
    ("funny", "What song would ruin the mood fastest if played during a dentist appointment?"),
    ("funny", "What mild inconvenience makes you disproportionately dramatic?"),
    ("funny", "What is the most chaotic thing you ever did out of pure boredom?"),
    ("funny", "If your search history became a movie trailer, what would the tagline be?"),
    ("funny", "What rule exists somewhere in your life strictly because of something you did?"),
    ("funny", "What snack disappears mysteriously fast only when you are home alone?"),
    # opinion (13)
    ("opinion", "Pineapple on pizza aside, what popular food opinion do you think is a scam?"),
    ("opinion", "Should voice notes longer than 60 seconds legally require a written summary?"),
    ("opinion", "Is arriving 5 minutes early polite, or secretly chaotic?"),
    ("opinion", "What movie or show did everyone praise that you tapped out of halfway?"),
    ("opinion", "What everyday etiquette rule do too many people ignore in shared spaces?"),
    ("opinion", "Is texting 'k' always passive-aggressive or sometimes just efficient?"),
    ("opinion", "What trend from five years ago aged much better than people expected?"),
    ("opinion", "Should recliners on short daytime flights stay upright?"),
    ("opinion", "What overrated adult purchase actually ended up worth every cent?"),
    ("opinion", "Which season has the worst weather pretending to be nice?"),
    ("opinion", "Should spoilers expire after two weeks or stay protected forever?"),
    ("opinion", "Is cereal technically cold soup, or should that question be banned?"),
    ("opinion", "What small daily habit quietly improves life more than big resolutions?"),
    # story (13)
    ("story", "Tell us about the closest you ever came to getting caught in a harmless fib."),
    ("story", "What trip or commute went sideways in a way that became funnier later?"),
    ("story", "Describe a time you confidently walked into the wrong place or wrong group."),
    ("story", "What was your biggest kitchen disaster when cooking for yourself or others?"),
    ("story", "Tell us about a stranger who accidentally made your week much better."),
    ("story", "What is a memory from school where everyone tried not to laugh and failed?"),
    ("story", "Describe the most improvised gift or apology you ever pulled off last minute."),
    ("story", "When did autocorrect or sending a message to the wrong chat betray you hardest?"),
    ("story", "What was the longest you ever spent trying to fix something super simple?"),
    ("story", "Tell us about a childhood rule you broke thinking nobody would notice."),
    ("story", "Describe a moment where trying to act cool backfired within five seconds."),
    ("story", "What lost item turned up in a ridiculous spot months or years later?"),
    ("story", "Tell us about an unexpected delay that led to a surprisingly good memory."),
)


def ensure_topics_seeded() -> tuple[int, int]:
    """Ensure all 40 default topics exist in PostgreSQL; returns (created_count, total_count)."""
    from apps.game.models import Topic

    existing_texts = set(Topic.objects.values_list("text", flat=True))
    to_create = [
        Topic(category=category, text=text, active=True)
        for category, text in TOPIC_SEEDS
        if text not in existing_texts
    ]
    if to_create:
        Topic.objects.bulk_create(to_create, ignore_conflicts=True)
    return len(to_create), Topic.objects.count()


def main() -> None:
    """CLI entrypoint for seeding default topics."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    import django

    django.setup()
    created, total = ensure_topics_seeded()
    print(f"Seeded topics: created={created}, total={total}")


if __name__ == "__main__":
    main()

