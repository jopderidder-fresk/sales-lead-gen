"""Seed non-sensitive defaults into the app_settings table.

Run after migrations:  python -m app.core.seed_defaults

Only inserts keys that don't already exist, so user-customised values
(set via the admin UI) are never overwritten.
"""

from __future__ import annotations

import asyncio
import os

import asyncpg

# Non-sensitive defaults to seed.  Values are read from env vars (matching
# the names used by config.py / pydantic-settings) with hardcoded fallbacks
# that mirror the defaults in config.py.
DEFAULTS: dict[str, str] = {
    # ── Usage limits ──────────────────────────────────────────────
    "limits.max_companies_per_discovery_run": os.environ.get(
        "MAX_COMPANIES_PER_DISCOVERY_RUN", "50"
    ),
    "limits.max_discovery_runs_per_day": os.environ.get(
        "MAX_DISCOVERY_RUNS_PER_DAY", "5"
    ),
    "limits.max_enrichments_per_day": os.environ.get(
        "MAX_ENRICHMENTS_PER_DAY", "100"
    ),
    "limits.max_scrapes_per_day": os.environ.get(
        "MAX_SCRAPES_PER_DAY", "50"
    ),
    "limits.max_monitoring_companies_per_run": os.environ.get(
        "MAX_MONITORING_COMPANIES_PER_RUN", "200"
    ),
    "limits.daily_api_cost_limit": os.environ.get(
        "DAILY_API_COST_LIMIT", "25.0"
    ),
    # ── LinkedIn scraping ─────────────────────────────────────────
    "linkedin.interval_days": "7",
    "linkedin.days_back": "7",
    # ── Slack timing ──────────────────────────────────────────────
    "slack.digest_hour": os.environ.get("SLACK_DIGEST_HOUR", "9"),
    "slack.weekly_day": os.environ.get("SLACK_WEEKLY_DAY", "0"),
    # ── Job enabled states (all enabled by default) ───────────────
    "job.enabled.discover-companies": "true",
    "job.enabled.enrich-all-discovered": "true",
    "job.enabled.monitor-high-priority": "true",
    "job.enabled.monitor-standard": "true",
    "job.enabled.process-signal-queue": "true",
    "job.enabled.recalculate-all-scores": "true",
    "job.enabled.deduplicate-companies": "true",
    "job.enabled.sync-to-crm": "true",
    "job.enabled.slack-daily-digest": "true",
    "job.enabled.slack-weekly-summary": "true",
    "job.enabled.scrape-linkedin-batch": "true",
    "job.enabled.cleanup-stale-jobs": "true",
}


async def seed() -> None:
    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER", "sales"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        database=os.environ.get("POSTGRES_DB", "sales"),
    )
    try:
        inserted = 0
        for key, value in DEFAULTS.items():
            result = await conn.execute(
                "INSERT INTO app_settings (key, value, updated_at) "
                "VALUES ($1, $2, NOW()) "
                "ON CONFLICT (key) DO NOTHING",
                key,
                value,
            )
            if result == "INSERT 0 1":
                inserted += 1
        skipped = len(DEFAULTS) - inserted
        print(f"[seed_defaults] Seeded {inserted} new defaults ({skipped} already existed)")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
