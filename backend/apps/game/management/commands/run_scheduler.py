"""Management command polling Redis ZSET `game:deadlines` for due phase transitions."""

from __future__ import annotations

import logging
import signal
import time
from types import FrameType

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from apps.game.scheduler import claim_due_deadlines, reconcile_active_deadlines

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Run the atomic game phase deadline scheduler loop."""

    help = "Run the Spot the Bot deadline scheduler process."

    def __init__(self) -> None:
        super().__init__()
        self._running = True
        self._ticks_since_reconcile = 0

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run a single reconcile + claim tick and exit (useful for testing).",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=float(getattr(settings, "SCHEDULER_POLL_INTERVAL_SECONDS", 0.5)),
            help="Polling interval in seconds (default: 0.5).",
        )

    def _handle_stop(self, signum: int, frame: FrameType | None) -> None:
        self._running = False

    def run_tick(self, *, reconcile: bool = False) -> int:
        """Execute one scheduler tick; returns number of due transitions claimed."""
        if reconcile or self._ticks_since_reconcile >= 20:
            try:
                reconcile_active_deadlines()
            except Exception:
                logger.exception("Failed reconciling active round deadlines")
            self._ticks_since_reconcile = 0
        else:
            self._ticks_since_reconcile += 1

        try:
            return claim_due_deadlines()
        except Exception:
            logger.exception("Error while claiming due deadlines")
            return 0

    def handle(self, *args: object, **options: object) -> None:
        once = bool(options.get("once", False))
        interval = float(options.get("interval", 0.5))  # type: ignore[arg-type]

        signal.signal(signal.SIGTERM, self._handle_stop)
        signal.signal(signal.SIGINT, self._handle_stop)

        self.stdout.write(self.style.SUCCESS("Scheduler started (Redis ZSET deadline poller)."))
        if once:
            self.run_tick(reconcile=True)
            return

        # Reconcile Postgres active rounds into Redis on startup before entering loop.
        self.run_tick(reconcile=True)
        while self._running:
            time.sleep(interval)
            if not self._running:
                break
            self.run_tick()

        logger.info("Scheduler stopped cleanly.")
