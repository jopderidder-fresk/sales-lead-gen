"""Placeholder tasks for all 8 scheduled jobs (PRD §10).

Each task logs a not-implemented message and returns immediately.
Replace with real implementations in their respective tickets.
"""

import structlog

from app.core.celery_app import celery_app
from app.tasks.base import BaseTask, check_job_enabled

logger = structlog.get_logger(__name__)


def _placeholder(name: str) -> str:
    logger.info("task.placeholder", task_name=name, message="Not yet implemented")
    return f"{name}: not yet implemented"


# --- Discovery queue ---------------------------------------------------------
# discover_companies moved to app.tasks.discovery (LP-015)


@celery_app.task(base=BaseTask, name="app.tasks.discovery.deduplicate_companies")
def deduplicate_companies() -> str:
    """LP-019: Weekly deduplication pass over the companies table."""
    if not check_job_enabled("deduplicate-companies"):
        return "deduplicate-companies: skipped — job disabled"
    return _placeholder("deduplicate_companies")


# --- Enrichment queue --------------------------------------------------------


# Contact finding → app.tasks.contacts.find_company_contacts
# LLM enrichment → app.tasks.enrichment.enrich_company

# recalculate_all_scores moved to app.tasks.lead_scoring (LP-027)


# --- Monitoring queue — see app.tasks.monitoring (LP-023) ---------------------


# --- LLM queue — see app.tasks.llm (LP-026) ----------------------------------


# --- Integrations queue — see app.tasks.integrations (LP-030) ----------------
