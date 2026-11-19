"""Django management command to seed default game topics idempotently."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from scripts.seed_topics import ensure_topics_seeded


class Command(BaseCommand):
    """Seed default party game topics into the database."""

    help = "Seed 40 default party topics into the database idempotently."

    def handle(self, *args, **options) -> None:
        created, total = ensure_topics_seeded()
        self.stdout.write(
            self.style.SUCCESS(
                f"Default topics seeded successfully: {created} created, {total} total."
            )
        )
