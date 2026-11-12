"""Phase 0 placeholder scheduler management command (deadline polling added in Phase 3)."""

from __future__ import annotations

import logging
import signal
import time
from types import FrameType

from django.core.management.base import BaseCommand, CommandParser

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Run the game phase deadline scheduler loop."""

    help = "Run the Spot the Bot deadline scheduler process."

    def __init__(self) -> None:
        super().__init__()
        self._running = True

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run a single scheduler tick and exit (useful for testing).",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=0.5,
            help="Polling interval in seconds (default: 0.5).",
        )

    def _handle_stop(self, signum: int, frame: FrameType | None) -> None:
        self._running = False

    def run_tick(self) -> int:
        """Execute one scheduler tick; returns number of due transitions claimed."""
        return 0

    def handle(self, *args: object, **options: object) -> None:
        once = bool(options.get("once", False))
        interval = float(options.get("interval", 0.5))  # type: ignore[arg-type]

        signal.signal(signal.SIGTERM, self._handle_stop)
        signal.signal(signal.SIGINT, self._handle_stop)

        self.stdout.write(self.style.SUCCESS("Scheduler started (Phase 0 placeholder)."))
        if once:
            self.run_tick()
            return

        while self._running:
            self.run_tick()
            time.sleep(interval)

        logger.info("Scheduler stopped cleanly.")
