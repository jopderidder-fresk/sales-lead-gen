"""Shared utility functions."""

from datetime import UTC, datetime

# The escape character used by escape_like(). Pass to ilike(..., escape=LIKE_ESCAPE).
LIKE_ESCAPE = "\\"


def utcnow() -> datetime:
    """Return the current UTC time as a naive datetime (no deprecation warning).

    Drop-in replacement for ``datetime.utcnow()`` that avoids the Python 3.12
    deprecation warning while still returning a naive datetime compatible with
    TIMESTAMP WITHOUT TIME ZONE columns.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def today_start_utc() -> datetime:
    """Return midnight UTC of the current day as a naive datetime (matches TIMESTAMP WITHOUT TIME ZONE columns)."""
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)


def escape_like(value: str) -> str:
    """Escape SQL LIKE special characters so user input is treated as a literal string.

    Callers must also pass ``escape=LIKE_ESCAPE`` to ``ilike()``/``like()``
    so PostgreSQL knows which escape character to use.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
