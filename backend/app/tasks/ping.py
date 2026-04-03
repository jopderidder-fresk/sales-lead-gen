"""Simple round-trip test task to verify Celery connectivity."""

from app.core.celery_app import celery_app
from app.tasks.base import BaseTask


@celery_app.task(base=BaseTask, name="app.tasks.ping")
def ping() -> str:
    """Return 'pong' — verifies broker → worker → result backend round-trip."""
    return "pong"
