import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog

from app.core.config import settings

NL_TZ = ZoneInfo("Europe/Amsterdam")


def _nl_timestamper(
    logger: object, method_name: str, event_dict: dict
) -> dict:
    """Add an ISO-8601 timestamp in Europe/Amsterdam (handles CET/CEST)."""
    event_dict["timestamp"] = datetime.now(NL_TZ).isoformat()
    return event_dict


def setup_logging() -> None:
    """Configure structured JSON logging with structlog."""
    log_level = getattr(logging, settings.app_log_level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            _nl_timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
            if settings.app_env == "production"
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
