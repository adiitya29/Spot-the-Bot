"""Management command to delete expired room data and retain consented replays."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.rooms.models import Room


class Command(BaseCommand):
    """Prune inactive/expired rooms and associated game records past retention threshold."""

    help = "Delete expired rooms and ephemeral game data past the retention period."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--older-than-days",
            type=int,
            default=7,
            help="Prune rooms created more than N days ago (default: 7).",
        )
        parser.add_argument(
            "--older-than-hours",
            type=int,
            default=None,
            help="Prune rooms created more than N hours ago (overrides days if set).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate deletion and print count without deleting database records.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        now = timezone.now()
        hours = options.get("older_than_hours")
        if hours is not None:
            cutoff = now - timedelta(hours=hours)
            delta_desc = f"{hours} hours"
        else:
            days = options["older_than_days"]
            cutoff = now - timedelta(days=days)
            delta_desc = f"{days} days"

        dry_run = options.get("dry_run", False)

        expired_rooms = Room.objects.filter(created_at__lt=cutoff)
        total_rooms = expired_rooms.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Would delete {total_rooms} room(s) "
                    f"created before {cutoff} ({delta_desc} old)."
                )
            )
            return

        deleted_counts, _ = expired_rooms.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deleted {total_rooms} room(s) "
                f"({deleted_counts} related DB records) older than {delta_desc}."
            )
        )
