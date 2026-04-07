"""Celery application configuration.

Entry point for workers:  celery -A app.tasks.worker worker
Entry point for beat:     celery -A app.tasks.worker beat
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery("sales")

celery_app.conf.update(
    # Broker & result backend (Redis)
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,

    # Serialization — JSON only for security (no pickle)
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone — Europe/Amsterdam handles CET (UTC+1) / CEST (UTC+2) automatically
    timezone="Europe/Amsterdam",
    enable_utc=True,

    # Task routing by name prefix → dedicated queues
    task_routes={
        "app.tasks.discovery.*": {"queue": "discovery"},
        "app.tasks.enrichment.*": {"queue": "enrichment"},
        "app.tasks.contacts.*": {"queue": "enrichment"},
        "app.tasks.scraping.*": {"queue": "monitoring"},
        "app.tasks.monitoring.*": {"queue": "monitoring"},
        "app.tasks.llm.*": {"queue": "llm"},
        "app.tasks.lead_scoring.*": {"queue": "enrichment"},
        "app.tasks.linkedin.*": {"queue": "monitoring"},
        "app.tasks.integrations.*": {"queue": "integrations"},
    },

    # Task execution defaults
    task_track_started=True,
    task_time_limit=600,       # 10 min hard kill
    task_soft_time_limit=540,  # 9 min soft limit (raises SoftTimeLimitExceeded)

    # Worker tuning
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_concurrency=4,

    # Result expiry
    result_expires=86400,  # 24 hours

    # Beat scheduler — store schedule state in Redis, not a local file
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=settings.celery_broker_url,
    # Lock timeout must exceed the longest possible idle period between ticks.
    # Default (5 * max_loop_interval = 25 min) caused LockNotOwnedError crashes
    # when beat was paused for hours. 2 hours gives ample headroom.
    redbeat_lock_timeout=60 * 60 * 2,

    # Task module discovery
    include=[
        "app.tasks.ping",
        "app.tasks.placeholders",
        "app.tasks.llm",
        "app.tasks.discovery",
        "app.tasks.enrichment",
        "app.tasks.contacts",
        "app.tasks.scraping",
        "app.tasks.monitoring",
        "app.tasks.lead_scoring",
        "app.tasks.linkedin",
        "app.tasks.integrations",
    ],

    # ---------------------------------------------------------------------------
    # Beat schedule — placeholder entries for all 8 periodic tasks (PRD §10)
    # ---------------------------------------------------------------------------
    beat_schedule={
        "discover-companies": {
            "task": "app.tasks.discovery.discover_companies",
            "schedule": crontab(hour=2, minute=0),  # Daily 02:00 NL time
            "options": {"queue": "discovery"},
        },
        "enrich-all-discovered": {
            "task": "app.tasks.enrichment.enrich_all_discovered",
            "schedule": crontab(hour=4, minute=0),  # Daily 04:00 NL time
            "options": {"queue": "enrichment"},
        },
        "monitor-high-priority": {
            "task": "app.tasks.monitoring.monitor_high_priority",
            "schedule": crontab(minute=0, hour="*/4"),  # Every 4 hours
            "options": {"queue": "monitoring"},
        },
        "monitor-standard": {
            "task": "app.tasks.monitoring.monitor_standard",
            "schedule": crontab(hour=6, minute=0),  # Daily 06:00 NL time
            "options": {"queue": "monitoring"},
        },
        "process-signal-queue": {
            "task": "app.tasks.llm.process_signal_queue",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes
            "options": {"queue": "llm"},
        },
        "recalculate-all-scores": {
            "task": "app.tasks.lead_scoring.recalculate_all_lead_scores",
            "schedule": crontab(hour=8, minute=0),  # Daily 08:00 NL time
            "options": {"queue": "enrichment"},
        },
        "deduplicate-companies": {
            "task": "app.tasks.discovery.deduplicate_companies",
            "schedule": crontab(hour=1, minute=0, day_of_week="sunday"),  # Weekly Sun 01:00 NL time
            "options": {"queue": "discovery"},
        },
        # "sync-to-crm" removed — companies should only be pushed to
        # ClickUp manually via the API endpoint.
        "slack-daily-digest": {
            "task": "app.tasks.integrations.slack_daily_digest",
            "schedule": crontab(hour=9, minute=0),  # Daily 09:00 NL time
            "options": {"queue": "integrations"},
        },
        "slack-weekly-summary": {
            "task": "app.tasks.integrations.slack_weekly_summary",
            "schedule": crontab(hour=9, minute=0, day_of_week="monday"),  # Monday 09:00 NL time
            "options": {"queue": "integrations"},
        },
        "scrape-linkedin-batch": {
            "task": "app.tasks.linkedin.scrape_linkedin_batch",
            "schedule": crontab(hour=5, minute=0),  # Daily 05:00 NL time (interval controlled by DB setting)
            "options": {"queue": "monitoring"},
        },
        "cleanup-stale-jobs": {
            "task": "app.tasks.enrichment.cleanup_stale_jobs",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
            "options": {"queue": "enrichment"},
        },
    },
)
