"""Celery worker entry point.

Used by the CLI:
    celery -A app.tasks.worker worker --loglevel=info
    celery -A app.tasks.worker beat --loglevel=info
"""

from app.core.celery_app import celery_app  # noqa: F401
from app.core.logging import setup_logging

# Ensure structured logging is configured for the worker process
setup_logging()
