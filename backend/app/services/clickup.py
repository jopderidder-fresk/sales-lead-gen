"""ClickUp integration service — syncs qualified leads to ClickUp tasks.

Orchestrates the ClickUp API client with database operations:
- Creates tasks for companies that qualify (lead_score >= threshold)
- Updates existing tasks when new signals arrive
- Stores the clickup_task_id back on the Company record
- Finds existing tasks by company domain to prevent duplicates
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.utils import utcnow
from app.models.company import Company
from app.models.contact import Contact
from app.models.signal import Signal
from app.services.api.clickup import ClickUpClient, ClickUpNotFoundError, ClickUpTask

logger = get_logger(__name__)

# Default score threshold for pushing to ClickUp
DEFAULT_QUALIFY_THRESHOLD = 50.0


class ClickUpSyncResult:
    """Result of a sync_to_clickup run."""

    def __init__(self) -> None:
        self.created: list[tuple[int, str]] = []  # (company_id, task_id)
        self.updated: list[tuple[int, str]] = []
        self.skipped: list[int] = []
        self.errors: list[tuple[int, str]] = []  # (company_id, error_message)

    def summary(self) -> str:
        parts = [
            f"created={len(self.created)}",
            f"updated={len(self.updated)}",
            f"skipped={len(self.skipped)}",
            f"errors={len(self.errors)}",
        ]
        return f"ClickUp sync: {', '.join(parts)}"


class ClickUpService:
    """Business logic for syncing companies to ClickUp."""

    def __init__(
        self,
        client: ClickUpClient,
        *,
        domain_field_id: str = "",
        qualify_threshold: float = DEFAULT_QUALIFY_THRESHOLD,
    ) -> None:
        self._client = client
        self._domain_field_id = domain_field_id
        self._qualify_threshold = qualify_threshold

    async def close(self) -> None:
        await self._client.close()

    # ------------------------------------------------------------------
    # High-level sync: process all qualifying companies
    # ------------------------------------------------------------------

    async def sync_qualified_companies(self, session: AsyncSession) -> ClickUpSyncResult:
        """Find all qualifying companies and create/update ClickUp tasks.

        A company qualifies when:
        - lead_score >= threshold
        - status is 'qualified' or 'pushed'

        If the company already has a clickup_task_id, update the task.
        Otherwise, create a new one.
        """
        result = ClickUpSyncResult()

        stmt = select(Company).where(
            Company.lead_score >= self._qualify_threshold,
            Company.status.in_(["qualified", "pushed"]),
        )
        companies = (await session.execute(stmt)).scalars().all()

        for company in companies:
            try:
                if company.clickup_task_id:
                    await self._update_existing_task(session, company, result)
                else:
                    await self._create_new_task(session, company, result)
            except Exception as exc:
                logger.error(
                    "clickup.sync_error",
                    company_id=company.id,
                    domain=company.domain,
                    error=str(exc),
                )
                result.errors.append((company.id, str(exc)))

        return result

    # ------------------------------------------------------------------
    # Single-company operations
    # ------------------------------------------------------------------

    async def push_company(
        self,
        session: AsyncSession,
        company_id: int,
    ) -> ClickUpTask:
        """Push a single company to ClickUp (create or update).

        Args:
            session: Database session.
            company_id: The company ID to push.

        Returns:
            The created/updated ClickUp task.
        """
        stmt = select(Company).where(Company.id == company_id)
        company = (await session.execute(stmt)).scalar_one_or_none()
        if company is None:
            raise ValueError(f"Company {company_id} not found")

        if company.clickup_task_id:
            return await self._update_company_task(session, company)
        return await self._create_company_task(session, company)

    async def get_company_task(
        self,
        session: AsyncSession,
        company_id: int,
    ) -> ClickUpTask | None:
        """Retrieve the ClickUp task linked to a company.

        Returns None if the company has no clickup_task_id.
        """
        stmt = select(Company).where(Company.id == company_id)
        company = (await session.execute(stmt)).scalar_one_or_none()
        if company is None:
            raise ValueError(f"Company {company_id} not found")

        if not company.clickup_task_id:
            return None

        try:
            return await self._client.get_task(company.clickup_task_id)
        except ClickUpNotFoundError:
            logger.warning(
                "clickup.task_not_found",
                company_id=company.id,
                task_id=company.clickup_task_id,
            )
            return None

    async def sync_status_from_clickup(
        self,
        session: AsyncSession,
        company_id: int,
    ) -> ClickUpTask | None:
        """Fetch the ClickUp task and sync its status to the local database.

        Updates company.clickup_status if it differs from the ClickUp task status.
        Does NOT push any status change back to ClickUp.
        """
        stmt = select(Company).where(Company.id == company_id)
        company = (await session.execute(stmt)).scalar_one_or_none()
        if company is None:
            raise ValueError(f"Company {company_id} not found")

        if not company.clickup_task_id:
            return None

        try:
            task = await self._client.get_task(company.clickup_task_id)
        except ClickUpNotFoundError:
            logger.warning(
                "clickup.task_not_found",
                company_id=company.id,
                task_id=company.clickup_task_id,
            )
            return None

        if task.status and task.status != company.clickup_status:
            old_status = company.clickup_status
            company.clickup_status = task.status
            await session.commit()
            logger.info(
                "clickup.status_synced",
                company_id=company.id,
                old_status=old_status,
                new_status=task.status,
            )

        return task

    async def find_existing_task(self, domain: str) -> ClickUpTask | None:
        """Search ClickUp for an existing task by company domain.

        Requires domain_field_id to be configured.
        """
        if not self._domain_field_id:
            logger.warning("clickup.no_domain_field_id", msg="Cannot search by domain without domain_field_id")
            return None

        return await self._client.find_task_by_custom_field(
            field_id=self._domain_field_id,
            value=domain,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _create_new_task(
        self,
        session: AsyncSession,
        company: Company,
        result: ClickUpSyncResult,
    ) -> None:
        """Create a ClickUp task and store the task ID on the company."""
        # Check for existing task by domain first (deduplication)
        existing = await self.find_existing_task(company.domain)
        if existing:
            company.clickup_task_id = existing.id
            company.clickup_task_url = existing.url
            await session.commit()
            result.skipped.append(company.id)
            logger.info(
                "clickup.found_existing",
                company_id=company.id,
                task_id=existing.id,
            )
            return

        task = await self._create_company_task(session, company)
        result.created.append((company.id, task.id))

    async def _update_existing_task(
        self,
        session: AsyncSession,
        company: Company,
        result: ClickUpSyncResult,
    ) -> None:
        """Update an existing ClickUp task with latest company data."""
        task = await self._update_company_task(session, company)
        result.updated.append((company.id, task.id))

    async def _create_company_task(
        self,
        session: AsyncSession,
        company: Company,
    ) -> ClickUpTask:
        """Build and create a ClickUp task for a company."""
        contact = await self._get_primary_contact(session, company.id)
        latest_signal = await self._get_latest_signal(session, company.id)

        custom_fields = self._build_custom_fields(company, contact, latest_signal)
        description = self._build_description(company, contact, latest_signal)

        task = await self._client.create_task(
            name=company.name,
            description=description,
            status="suspect",
            custom_fields=custom_fields,
        )

        # Store the task ID and URL on the company
        company.clickup_task_id = task.id
        company.clickup_task_url = task.url
        company.clickup_status = "suspect"
        company.status = "pushed"  # type: ignore[assignment]
        await session.commit()

        # Post all existing signals as activity comments on the new task
        uncommented = await self._get_uncommented_signals(session, company.id)
        if uncommented:
            await self._post_signals_as_comments(session, task.id, uncommented)

        logger.info(
            "clickup.task_created",
            company_id=company.id,
            task_id=task.id,
            task_url=task.url,
        )
        return task

    async def _update_company_task(
        self,
        session: AsyncSession,
        company: Company,
    ) -> ClickUpTask:
        """Update an existing ClickUp task with latest data."""
        contact = await self._get_primary_contact(session, company.id)
        latest_signal = await self._get_latest_signal(session, company.id)

        custom_fields = self._build_custom_fields(company, contact, latest_signal)

        task = await self._client.update_task(
            company.clickup_task_id,  # type: ignore[arg-type]
            custom_fields=custom_fields,
        )

        # Keep URL in sync
        if task.url and company.clickup_task_url != task.url:
            company.clickup_task_url = task.url
            await session.commit()

        # Post all new (uncommented) signals as activity comments
        uncommented = await self._get_uncommented_signals(session, company.id)
        if uncommented:
            await self._post_signals_as_comments(session, task.id, uncommented)

        logger.info(
            "clickup.task_updated",
            company_id=company.id,
            task_id=task.id,
        )
        return task

    async def _get_primary_contact(
        self,
        session: AsyncSession,
        company_id: int,
    ) -> Contact | None:
        """Get the highest-confidence contact for a company."""
        stmt = (
            select(Contact)
            .where(Contact.company_id == company_id)
            .order_by(Contact.confidence_score.desc().nullslast())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def _get_latest_signal(
        self,
        session: AsyncSession,
        company_id: int,
    ) -> Signal | None:
        """Get the most recent signal for a company."""
        stmt = (
            select(Signal)
            .where(Signal.company_id == company_id)
            .order_by(Signal.created_at.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def _get_uncommented_signals(
        self,
        session: AsyncSession,
        company_id: int,
    ) -> list[Signal]:
        """Get all signals for a company that haven't been posted as ClickUp comments yet."""
        stmt = (
            select(Signal)
            .where(
                Signal.company_id == company_id,
                Signal.crm_commented_at.is_(None),
                Signal.signal_type != "no_signal",
            )
            .order_by(Signal.created_at.asc())
        )
        return list((await session.execute(stmt)).scalars().all())

    async def _post_signals_as_comments(
        self,
        session: AsyncSession,
        task_id: str,
        signals: list[Signal],
    ) -> None:
        """Post each signal as a ClickUp activity comment and mark it as commented."""
        now = utcnow()
        for signal in signals:
            summary = signal.llm_summary or signal.signal_type.value
            comment = (
                f"## Signal: {signal.signal_type.value}\n\n"
                f"{summary}\n\n"
                f"**Score:** {signal.relevance_score or 'N/A'} | "
                f"**Detected:** {signal.created_at.strftime('%Y-%m-%d %H:%M')}"
            )
            try:
                await self._client.add_comment(task_id, comment)
                signal.crm_commented_at = now
            except Exception as exc:
                logger.error(
                    "clickup.comment_failed",
                    task_id=task_id,
                    signal_id=signal.id,
                    error=str(exc),
                )
        await session.commit()

    def _build_custom_fields(
        self,
        company: Company,
        contact: Contact | None,
        signal: Signal | None,
    ) -> list[dict[str, Any]]:
        """Build ClickUp custom field values from company data.

        Only includes fields that have a configured field ID. The field IDs
        are workspace-specific and must be configured by the user.
        """
        fields: list[dict[str, Any]] = []

        # Only add the domain field if we have a field ID for it
        if self._domain_field_id:
            fields.append({"id": self._domain_field_id, "value": company.domain})

        return fields

    def _build_description(
        self,
        company: Company,
        contact: Contact | None,
        signal: Signal | None,
    ) -> str:
        """Build a markdown description for the ClickUp task."""
        lines = [
            f"# {company.name}",
            f"**Domain:** {company.domain}",
        ]

        if company.industry:
            lines.append(f"**Industry:** {company.industry}")
        if company.size:
            lines.append(f"**Size:** {company.size}")
        if company.location:
            lines.append(f"**Location:** {company.location}")
        if company.lead_score is not None:
            lines.append(f"**Lead Score:** {company.lead_score:.0f}")
        if company.icp_score is not None:
            lines.append(f"**ICP Score:** {company.icp_score:.0f}")

        if contact:
            lines.append("")
            lines.append("## Primary Contact")
            lines.append(f"**Name:** {contact.name}")
            if contact.title:
                lines.append(f"**Title:** {contact.title}")
            if contact.email:
                lines.append(f"**Email:** {contact.email}")
            if contact.phone:
                lines.append(f"**Phone:** {contact.phone}")
            if contact.linkedin_url:
                lines.append(f"**LinkedIn:** {contact.linkedin_url}")

        if signal:
            lines.append("")
            lines.append("## Latest Signal")
            lines.append(f"**Type:** {signal.signal_type.value}")
            if signal.llm_summary:
                lines.append(f"**Summary:** {signal.llm_summary}")
            if signal.relevance_score is not None:
                lines.append(f"**Relevance:** {signal.relevance_score:.0f}")
            lines.append(f"**Detected:** {signal.created_at.strftime('%Y-%m-%d %H:%M')}")

        lines.append("")
        lines.append(f"---\n*Synced from LeadPulse on {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

        return "\n".join(lines)
