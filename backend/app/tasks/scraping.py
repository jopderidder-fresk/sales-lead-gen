"""Homepage scraping Celery task.

Scrapes the homepage of a company's domain via Firecrawl and extracts the
LinkedIn company URL if present.  Does NOT create Signal records — signals
are generated exclusively from LinkedIn post data.
"""

import structlog
from sqlalchemy import func, select

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import async_session_factory, run_async
from app.core.utils import today_start_utc, utcnow
from app.models.company import Company
from app.models.enums import ScrapeJobStatus
from app.models.scrape_job import ScrapeJob
from app.services.api.errors import APIError
from app.services.api.firecrawl import FirecrawlClient
from app.tasks.base import BaseTask
from app.utils.linkedin import extract_linkedin_company_url

logger = structlog.get_logger(__name__)


async def _scrape_company(company_id: int, scrape_job_id: int) -> str:
    """Scrape the homepage only and extract LinkedIn URL."""
    async with async_session_factory() as session:
        company = (
            await session.execute(select(Company).where(Company.id == company_id))
        ).scalar_one_or_none()

        if company is None:
            return f"company {company_id} not found"

        job = (
            await session.execute(select(ScrapeJob).where(ScrapeJob.id == scrape_job_id))
        ).scalar_one_or_none()

        if job is None:
            return f"scrape job {scrape_job_id} not found"

        # Enforce daily scrape limit at task level
        scrapes_today = (
            await session.execute(
                select(func.count()).select_from(ScrapeJob).where(
                    ScrapeJob.created_at >= today_start_utc(),
                    ScrapeJob.status != ScrapeJobStatus.FAILED,
                )
            )
        ).scalar_one()
        if scrapes_today > settings.max_scrapes_per_day:
            job.status = ScrapeJobStatus.FAILED
            job.error_message = f"Daily scrape limit reached ({settings.max_scrapes_per_day}/day)"
            job.completed_at = utcnow()
            await session.commit()
            logger.warning("scrape.daily_limit_reached", company_id=company_id, limit=settings.max_scrapes_per_day)
            return f"company={company_id} error=daily scrape limit reached"

        job.status = ScrapeJobStatus.RUNNING
        job.started_at = utcnow()
        await session.commit()

        from app.core.app_settings_store import DB_FIRECRAWL_API_KEY, get_effective_secret

        firecrawl_key = await get_effective_secret(DB_FIRECRAWL_API_KEY, settings.firecrawl_api_key)
        client = FirecrawlClient(api_key=firecrawl_key)
        try:
            homepage_url = f"https://{company.domain}"
            credits_used = 0.0
            linkedin_found: str | None = None

            # Scrape only the homepage
            try:
                sr = await client.scrape(homepage_url)
                credits_used += 1.0
            except Exception as exc:
                logger.warning("scrape.homepage_failed", company_id=company_id, error=str(exc))
                job.status = ScrapeJobStatus.FAILED
                job.error_message = f"Homepage scrape failed: {exc}"
                job.completed_at = utcnow()
                await session.commit()
                return f"company={company_id} error={exc}"

            markdown = sr.markdown or ""
            scrape_ok = len(markdown.strip()) >= 50

            if scrape_ok:
                # Extract LinkedIn company URL from homepage content
                linkedin_found = extract_linkedin_company_url(markdown)
                if linkedin_found and not company.linkedin_url:
                    company.linkedin_url = linkedin_found
                    logger.info(
                        "scrape.linkedin_url_found",
                        company_id=company_id,
                        linkedin_url=linkedin_found,
                    )

                # Generate / update company_info from homepage content
                try:
                    from app.services.llm import create_llm_client

                    llm = await create_llm_client()
                    try:
                        profile = await llm.generate_company_profile(markdown)
                        company.company_info = profile.model_dump()
                        logger.info("scrape.company_info_generated", company_id=company_id)
                    finally:
                        await llm.close()
                except Exception as exc:
                    logger.warning(
                        "scrape.company_info_failed",
                        company_id=company_id,
                        error=str(exc),
                    )

            job.pages_scraped = 1
            job.credits_used = credits_used
            job.completed_at = utcnow()

            if not scrape_ok:
                job.status = ScrapeJobStatus.FAILED
                job.error_message = "No page content could be scraped — check Firecrawl API key and credits"
            else:
                job.status = ScrapeJobStatus.COMPLETED

            await session.commit()

            parts = [f"company={company_id}", f"credits={credits_used}"]
            if linkedin_found:
                parts.append(f"linkedin={linkedin_found}")
            return " ".join(parts)
        except (APIError, TimeoutError) as exc:
            job.status = ScrapeJobStatus.FAILED
            job.error_message = str(exc)[:500]
            job.completed_at = utcnow()
            await session.commit()
            return f"company={company_id} error={exc}"
        finally:
            await client.close()


@celery_app.task(
    base=BaseTask,
    name="app.tasks.scraping.trigger_company_scrape",
    acks_late=True,
    time_limit=360,
    soft_time_limit=300,
)
def trigger_company_scrape(company_id: int, scrape_job_id: int) -> str:
    """Scrape a company's domain via Firecrawl and record results.

    Pure scraping only. Does not generate company profiles,
    analyze signals, or trigger enrichment/contacts.
    """
    result = run_async(_scrape_company(company_id, scrape_job_id))

    from app.tasks.lead_scoring import recalculate_company_score

    recalculate_company_score.delay(company_id)

    return result
