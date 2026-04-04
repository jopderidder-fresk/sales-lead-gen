"""Persistent key-value settings backed by the app_settings table.

Use this to store runtime-configurable settings that must survive restarts,
such as integration webhook URLs entered through the admin UI.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting

_log = logging.getLogger(__name__)

# ── DB key constants (shared between API endpoints and task helpers) ──

DB_LLM_PROVIDER = "apikeys.llm_provider"
DB_ANTHROPIC_API_KEY = "apikeys.anthropic_api_key"
DB_OPENROUTER_API_KEY = "apikeys.openrouter_api_key"
DB_OPENROUTER_MODEL = "apikeys.openrouter_model"
DB_GEMINI_API_KEY = "apikeys.gemini_api_key"
DB_FIRECRAWL_API_KEY = "apikeys.firecrawl_api_key"
DB_HUNTER_IO_API_KEY = "apikeys.hunter_io_api_key"
DB_APOLLO_API_KEY = "apikeys.apollo_api_key"
DB_SCRAPIN_API_KEY = "apikeys.scrapin_api_key"
DB_BEDRIJFSDATA_API_KEY = "apikeys.bedrijfsdata_api_key"
DB_APIFY_API_TOKEN = "apikeys.apify_api_token"

DB_LINKEDIN_INTERVAL_DAYS = "linkedin.interval_days"
DB_LINKEDIN_DAYS_BACK = "linkedin.days_back"
DB_LINKEDIN_DAILY_SCRAPE_LIMIT = "linkedin.daily_scrape_limit"
DB_LINKEDIN_LAST_BATCH_RUN = "linkedin.last_batch_run"

LINKEDIN_DEFAULT_INTERVAL_DAYS = 7
LINKEDIN_DEFAULT_DAYS_BACK = 7
LINKEDIN_DEFAULT_DAILY_SCRAPE_LIMIT = 50

# Usage limits
DB_LIMITS_MAX_COMPANIES_PER_DISCOVERY_RUN = "limits.max_companies_per_discovery_run"
DB_LIMITS_MAX_DISCOVERY_RUNS_PER_DAY = "limits.max_discovery_runs_per_day"
DB_LIMITS_MAX_ENRICHMENTS_PER_DAY = "limits.max_enrichments_per_day"
DB_LIMITS_MAX_SCRAPES_PER_DAY = "limits.max_scrapes_per_day"
DB_LIMITS_MAX_MONITORING_COMPANIES_PER_RUN = "limits.max_monitoring_companies_per_run"
DB_LIMITS_DAILY_API_COST_LIMIT = "limits.daily_api_cost_limit"

# Slack timing
DB_SLACK_DIGEST_HOUR = "slack.digest_hour"
DB_SLACK_WEEKLY_DAY = "slack.weekly_day"


async def get_setting(session: AsyncSession, key: str) -> str | None:
    """Return the stored value for *key*, or None if not set."""
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else None


async def set_setting(session: AsyncSession, key: str, value: str | None) -> None:
    """Upsert *value* for *key* and commit."""
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        session.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    await session.commit()


# ── Encrypted helpers ──────────────────────────────────────────────
# Use these for API keys and other secrets so they are never stored
# as plaintext in the database.


async def get_encrypted_setting(session: AsyncSession, key: str) -> str | None:
    """Read a setting and decrypt it.  Returns None if the key is not set."""
    raw = await get_setting(session, key)
    if raw is None:
        return None
    return _try_decrypt(raw)


async def set_encrypted_setting(
    session: AsyncSession, key: str, value: str | None,
) -> None:
    """Encrypt *value* and persist it.  Pass None to clear the key."""
    if value is None:
        await set_setting(session, key, None)
        return
    encrypted = _try_encrypt(value)
    await set_setting(session, key, encrypted)


def _try_encrypt(plaintext: str) -> str:
    """Encrypt if a Fernet key is configured, otherwise return plaintext
    (development only — production enforces FERNET_KEY via config validation).
    """
    try:
        from app.core.encryption import encrypt
        return encrypt(plaintext)
    except Exception:
        _log.warning("app_settings_store: FERNET_KEY not set — storing value without encryption")
        return plaintext


# ── Job toggle helpers ────────────────────────────────────────────


def _job_setting_key(job_name: str) -> str:
    """Return the app_settings key for a job's enabled flag."""
    return f"job.enabled.{job_name}"


async def is_job_enabled(session: AsyncSession, job_name: str) -> bool:
    """Check whether a scheduled job is enabled.  Defaults to True."""
    val = await get_setting(session, _job_setting_key(job_name))
    if val is None:
        return True  # enabled by default
    return val.lower() in ("true", "1", "yes")


async def get_all_job_states(session: AsyncSession, job_names: list[str]) -> dict[str, bool]:
    """Return enabled state for all given job names."""
    result = await session.execute(
        select(AppSetting).where(
            AppSetting.key.in_([_job_setting_key(n) for n in job_names])
        )
    )
    rows = {row.key: row.value for row in result.scalars().all()}
    return {
        name: (rows.get(_job_setting_key(name)) or "true").lower() in ("true", "1", "yes")
        for name in job_names
    }


async def set_job_enabled(session: AsyncSession, job_name: str, enabled: bool) -> None:
    """Persist a job's enabled/disabled state."""
    await set_setting(session, _job_setting_key(job_name), str(enabled).lower())


def _try_decrypt(value: str) -> str:
    """Decrypt a Fernet token.  If the value is not a valid token (e.g. a
    legacy plaintext value or FERNET_KEY is missing), return it as-is.
    """
    # Fernet tokens always start with "gAAAAA"
    if not value.startswith("gAAAAA"):
        return value
    try:
        from app.core.encryption import decrypt
        return decrypt(value)
    except Exception:
        _log.warning("app_settings_store: failed to decrypt value — returning as-is")
        return value


# ── Effective-value helpers for Celery workers ────────────────────
# Tasks run in a separate process whose ``settings`` singleton is frozen
# at startup.  These helpers read the DB-stored value (set via the UI)
# first, falling back to the env-based ``settings`` attribute.


async def get_effective_setting(db_key: str, env_fallback: str) -> str:
    """Read a plain setting from the DB, fall back to env var."""
    from app.core.database import async_session_factory

    async with async_session_factory() as session:
        value = await get_setting(session, db_key)
        return value or env_fallback


async def get_effective_secret(db_key: str, env_fallback: str) -> str:
    """Read an encrypted setting from the DB, fall back to env var."""
    from app.core.database import async_session_factory

    async with async_session_factory() as session:
        value = await get_encrypted_setting(session, db_key)
        return value or env_fallback


# ── Startup loader ───────────────────────────────────────────────

# Maps DB keys to (settings attribute name, type cast).
_SETTINGS_MAP: dict[str, tuple[str, type]] = {
    DB_LIMITS_MAX_COMPANIES_PER_DISCOVERY_RUN: ("max_companies_per_discovery_run", int),
    DB_LIMITS_MAX_DISCOVERY_RUNS_PER_DAY: ("max_discovery_runs_per_day", int),
    DB_LIMITS_MAX_ENRICHMENTS_PER_DAY: ("max_enrichments_per_day", int),
    DB_LIMITS_MAX_SCRAPES_PER_DAY: ("max_scrapes_per_day", int),
    DB_LIMITS_MAX_MONITORING_COMPANIES_PER_RUN: ("max_monitoring_companies_per_run", int),
    DB_LIMITS_DAILY_API_COST_LIMIT: ("daily_api_cost_limit", float),
    DB_SLACK_DIGEST_HOUR: ("slack_digest_hour", int),
    DB_SLACK_WEEKLY_DAY: ("slack_weekly_day", int),
}


async def load_db_settings_into_config(session: AsyncSession) -> None:
    """Load non-sensitive DB settings into the settings singleton.

    Call at startup so the process uses DB-persisted values (set via admin UI)
    rather than just env-var defaults.
    """
    from app.core.config import settings

    for db_key, (attr_name, cast) in _SETTINGS_MAP.items():
        value = await get_setting(session, db_key)
        if value is not None:
            try:
                setattr(settings, attr_name, cast(value))
            except (ValueError, TypeError):
                _log.warning("load_db_settings: bad value for %s: %r", db_key, value)
