"""Celery background tasks for game lifecycle and state machine maintenance."""

from __future__ import annotations

from celery import shared_task

from apps.game.scheduler import claim_due_deadlines, reconcile_active_deadlines


@shared_task(name="apps.game.tasks.advance_due_rounds_task")
def advance_due_rounds_task() -> int:
    """Periodic Celery task fallback to advance any expired game round deadlines."""
    reconcile_active_deadlines()
    return claim_due_deadlines()
