"""ClickUp CRM provider — implements the CRMProvider protocol for ClickUp.

Wraps the existing ClickUpClient for HTTP calls and reads/writes from the
crm_integrations table instead of Company.clickup_* columns.
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
from app.models.crm_integration import CRMIntegration
from app.models.signal import Signal
from app.services.api.clickup import ClickUpClient, ClickUpNotFoundError, ClickUpTask
from app.services.crm.protocol import CRMSyncResult, CRMTask

logger = get_logger(__name__)

DEFAULT_QUALIFY_THRESHOLD = 50.0

PERSON_FIELD_KEYS = [
    "person_list_id",
    "person_email_field_id",
    "person_phone_field_id",
    "person_linkedin_field_id",
    "person_surname_field_id",
    "person_lastname_field_id",
    "person_role_field_id",
    "contact_relationship_field_id",
    "company_contact_field_id",
]


class ClickUpCRMProvider:
    """CRM provider implementation for ClickUp."""

    provider_name = "clickup"

    def __init__(
        self,
        client: ClickUpClient,
        *,
        domain_field_id: str = "",
        person_fields: dict[str, str] | None = None,
        qualify_threshold: float = DEFAULT_QUALIFY_THRESHOLD,
    ) -> None:
        self._client = client
        self._domain_field_id = domain_field_id
        pf = person_fields or {}
        self._person_list_id: str = pf.get("person_list_id", "")
        self._person_email_field_id: str = pf.get("person_email_field_id", "")
        self._person_phone_field_id: str = pf.get("person_phone_field_id", "")
        self._person_linkedin_field_id: str = pf.get("person_linkedin_field_id", "")
        self._person_surname_field_id: str = pf.get("person_surname_field_id", "")
        self._person_lastname_field_id: str = pf.get("person_lastname_field_id", "")
        self._person_role_field_id: str = pf.get("person_role_field_id", "")
        self._contact_relationship_field_id: str = pf.get("contact_relationship_field_id", "")
        self._company_contact_field_id: str = pf.get("company_contact_field_id", "")
        self._qualify_threshold = qualify_threshold

    async def close(self) -> None:
        await self._client.close()

    # ------------------------------------------------------------------
    # CRMProvider interface
    # ------------------------------------------------------------------

    async def push_company(self, session: AsyncSession, company_id: int) -> CRMTask:
        company = await self._load_company(session, company_id)
        if company is None:
            raise ValueError(f"Company {company_id} not found")

        integration = await self._get_integration(session, company_id)

        if integration:
            return await self._update_task(session, company, integration)

        existing = await self._find_existing_task(company.domain)
        match_strategy = "domain"
        if not existing:
            existing = await self._find_existing_task_by_name(session, company)
            match_strategy = "name"
        if existing:
            await self._link_existing(
                session, company, existing, match_strategy=match_strategy,
            )
            return self._to_crm_task(existing)

        return await self._create_task(session, company)

    async def sync_status(self, session: AsyncSession, company_id: int) -> CRMTask | None:
        company = await self._load_company(session, company_id)
        if company is None:
            raise ValueError(f"Company {company_id} not found")

        integration = await self._get_integration(session, company_id)
        if not integration:
            return None

        try:
            task = await self._client.get_task(integration.external_id)
        except ClickUpNotFoundError:
            logger.warning(
                "clickup.task_not_found",
                company_id=company.id,
                task_id=integration.external_id,
            )
            return None

        if task.status and task.status != integration.external_status:
            old_status = integration.external_status
            integration.external_status = task.status
            integration.synced_at = utcnow()
            # Write-through to legacy column
            company.clickup_status = task.status
            await session.commit()
            logger.info(
                "crm.status_synced",
                provider="clickup",
                company_id=company.id,
                old_status=old_status,
                new_status=task.status,
            )

        return self._to_crm_task(task)

    async def get_task(self, session: AsyncSession, company_id: int) -> CRMTask | None:
        integration = await self._get_integration(session, company_id)
        if not integration:
            return None

        try:
            task = await self._client.get_task(integration.external_id)
        except ClickUpNotFoundError:
            return None

        return self._to_crm_task(task)

    async def sync_qualified_companies(self, session: AsyncSession) -> CRMSyncResult:
        result = CRMSyncResult()

        stmt = select(Company).where(
            Company.lead_score >= self._qualify_threshold,
            Company.status.in_(["qualified", "pushed"]),
        )
        companies = (await session.execute(stmt)).scalars().all()

        # Pre-fetch all ClickUp tasks once so name-based dedup is O(1) per company
        task_name_cache = await self._build_task_name_cache()

        for company in companies:
            try:
                integration = await self._get_integration(session, company.id)
                if integration:
                    task = await self._update_task(session, company, integration)
                    result.updated.append((company.id, task.id))
                else:
                    existing = await self._find_existing_task(company.domain)
                    match_strategy = "domain"
                    if not existing:
                        existing = await self._find_existing_task_by_name(
                            session, company,
                            task_name_cache=task_name_cache,
                        )
                        match_strategy = "name"
                    if existing:
                        await self._link_existing(
                            session, company, existing,
                            match_strategy=match_strategy,
                        )
                        result.skipped.append(company.id)
                    else:
                        task = await self._create_task(session, company)
                        result.created.append((company.id, task.id))
            except Exception as exc:
                logger.error(
                    "crm.sync_error",
                    provider="clickup",
                    company_id=company.id,
                    error=str(exc),
                )
                result.errors.append((company.id, str(exc)))

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _to_crm_task(self, task: ClickUpTask) -> CRMTask:
        return CRMTask(
            id=task.id,
            name=task.name,
            status=task.status,
            url=task.url,
            provider=self.provider_name,
        )

    async def _load_company(self, session: AsyncSession, company_id: int) -> Company | None:
        stmt = select(Company).where(Company.id == company_id)
        return (await session.execute(stmt)).scalar_one_or_none()

    async def _get_integration(self, session: AsyncSession, company_id: int) -> CRMIntegration | None:
        stmt = select(CRMIntegration).where(
            CRMIntegration.company_id == company_id,
            CRMIntegration.provider == "clickup",
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def _create_task(self, session: AsyncSession, company: Company) -> CRMTask:
        contact = await self._get_primary_contact(session, company.id)
        latest_signal = await self._get_latest_signal(session, company.id)
        custom_fields = self._build_custom_fields(company)
        description = self._build_description(company, contact, latest_signal)

        task = await self._client.create_task(
            name=company.name,
            description=description,
            status="suspect",
            custom_fields=custom_fields,
        )

        # Create CRM integration record
        integration = CRMIntegration(
            company_id=company.id,
            provider="clickup",
            external_id=task.id,
            external_url=task.url,
            external_status="suspect",
        )
        session.add(integration)
        company.status = "pushed"  # type: ignore[assignment]
        # Write-through to legacy columns for backwards compatibility
        company.clickup_task_id = task.id
        company.clickup_task_url = task.url
        company.clickup_status = "suspect"
        await session.commit()

        # Post signals as comments
        uncommented = await self._get_uncommented_signals(session, company.id)
        if uncommented:
            await self._post_signals_as_comments(session, task.id, uncommented)

        # Push contacts as separate Person tasks
        await self._push_contacts(session, company.id, task.id)

        logger.info(
            "crm.task_created",
            provider="clickup",
            company_id=company.id,
            task_id=task.id,
        )

        return self._to_crm_task(task)

    async def _update_task(
        self, session: AsyncSession, company: Company, integration: CRMIntegration,
    ) -> CRMTask:
        custom_fields = self._build_custom_fields(company)

        task = await self._client.update_task(
            integration.external_id,
            custom_fields=custom_fields,
        )

        if task.url and integration.external_url != task.url:
            integration.external_url = task.url
            # Write-through to legacy column
            company.clickup_task_url = task.url
            await session.commit()

        # Post new signals as comments
        uncommented = await self._get_uncommented_signals(session, company.id)
        if uncommented:
            await self._post_signals_as_comments(session, task.id, uncommented)

        # Push contacts as separate Person tasks
        await self._push_contacts(session, company.id, integration.external_id)

        logger.info(
            "crm.task_updated",
            provider="clickup",
            company_id=company.id,
            task_id=task.id,
        )

        return self._to_crm_task(task)

    async def _link_existing(
        self, session: AsyncSession, company: Company, task: ClickUpTask,
        *, match_strategy: str = "",
    ) -> None:
        integration = CRMIntegration(
            company_id=company.id,
            provider=self.provider_name,
            external_id=task.id,
            external_url=task.url,
            external_status=task.status,
        )
        session.add(integration)
        # Write-through to legacy columns
        company.clickup_task_id = task.id
        company.clickup_task_url = task.url
        company.clickup_status = task.status
        await session.commit()
        logger.info(
            "crm.found_existing",
            provider=self.provider_name,
            company_id=company.id,
            task_id=task.id,
            match_strategy=match_strategy,
        )

    async def _build_task_name_cache(self) -> dict[str, ClickUpTask]:
        """Fetch all tasks from the ClickUp list into a name-keyed lookup."""
        cache: dict[str, ClickUpTask] = {}
        page = 0
        while True:
            task_list = await self._client.list_tasks(page=page)
            for task in task_list.tasks:
                cache.setdefault(task.name.lower(), task)
            if len(task_list.tasks) < 100:
                break
            page += 1
        return cache

    async def _find_existing_task(self, domain: str) -> ClickUpTask | None:
        if not self._domain_field_id:
            return None
        return await self._client.find_task_by_custom_field(
            field_id=self._domain_field_id, value=domain,
        )

    async def _find_existing_task_by_name(
        self,
        session: AsyncSession,
        company: Company,
        *,
        task_name_cache: dict[str, ClickUpTask] | None = None,
    ) -> ClickUpTask | None:
        """Check for an existing ClickUp task with the same name.

        First checks our DB for another company with the same name that
        already has a CRM integration.  Falls back to searching the ClickUp
        list by task name (or the pre-fetched cache when provided).
        """
        stmt = (
            select(CRMIntegration)
            .join(Company, CRMIntegration.company_id == Company.id)
            .where(
                Company.name == company.name,
                CRMIntegration.provider == self.provider_name,
                CRMIntegration.company_id != company.id,
            )
            .limit(1)
        )
        existing_integration = (await session.execute(stmt)).scalar_one_or_none()
        if existing_integration:
            try:
                return await self._client.get_task(existing_integration.external_id)
            except ClickUpNotFoundError:
                pass  # task was deleted in ClickUp, continue

        if task_name_cache is not None:
            return task_name_cache.get(company.name.lower())
        return await self._client.find_task_by_name(company.name)

    async def _get_primary_contact(self, session: AsyncSession, company_id: int) -> Contact | None:
        stmt = (
            select(Contact)
            .where(Contact.company_id == company_id)
            .order_by(Contact.confidence_score.desc().nullslast())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def _get_latest_signal(self, session: AsyncSession, company_id: int) -> Signal | None:
        stmt = (
            select(Signal)
            .where(Signal.company_id == company_id)
            .order_by(Signal.created_at.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def _get_uncommented_signals(self, session: AsyncSession, company_id: int) -> list[Signal]:
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
        self, session: AsyncSession, task_id: str, signals: list[Signal],
    ) -> None:
        now = utcnow()
        for signal in signals:
            summary = signal.llm_summary or signal.signal_type.value
            comment = (
                f"**Signal: {signal.signal_type.value}**\n\n"
                f"{summary}\n\n"
                f"Score: {signal.relevance_score or 'N/A'} | "
                f"Detected: {signal.created_at.strftime('%Y-%m-%d %H:%M')}"
            )
            try:
                await self._client.add_comment(task_id, comment)
                signal.crm_commented_at = now
            except Exception as exc:
                logger.error(
                    "crm.comment_failed",
                    provider="clickup",
                    task_id=task_id,
                    signal_id=signal.id,
                    error=str(exc),
                )
        await session.commit()

    # ------------------------------------------------------------------
    # Person / contact push helpers
    # ------------------------------------------------------------------

    async def _push_contacts(
        self, session: AsyncSession, company_id: int, company_task_id: str,
    ) -> None:
        """Create or update Person tasks for all contacts and link to company."""
        if not self._person_list_id:
            return  # person push not configured

        stmt = select(Contact).where(Contact.company_id == company_id)
        contacts = list((await session.execute(stmt)).scalars().all())
        if not contacts:
            return

        for contact in contacts:
            try:
                old_task_id = contact.clickup_task_id
                if contact.clickup_task_id:
                    # Update existing; may recreate if 404
                    await self._update_person_task(session, contact)
                else:
                    # Try dedup by email first
                    existing = await self._find_existing_person(contact)
                    if existing:
                        contact.clickup_task_id = existing.id
                        contact.clickup_task_url = existing.url
                    else:
                        await self._create_person_task(contact)

                # Link only when newly created/found, or recreated after 404
                if contact.clickup_task_id and contact.clickup_task_id != old_task_id:
                    await self._link_person_to_company(
                        contact.clickup_task_id, company_task_id,
                    )
            except Exception as exc:
                logger.error(
                    "crm.person_push_failed",
                    provider="clickup",
                    contact_id=contact.id,
                    error=str(exc),
                )

        await session.commit()

    async def _create_person_task(self, contact: Contact) -> None:
        """Create a Person task in ClickUp for a contact."""
        custom_fields = self._build_person_custom_fields(contact)
        task = await self._client.create_task(
            name=contact.name,
            list_id=self._person_list_id,
            status="prospect",
            custom_fields=custom_fields,
        )
        contact.clickup_task_id = task.id
        contact.clickup_task_url = task.url
        logger.info(
            "crm.person_created",
            provider="clickup",
            contact_id=contact.id,
            task_id=task.id,
        )

    async def _update_person_task(self, session: AsyncSession, contact: Contact) -> None:
        """Update an existing Person task with current contact data.

        If the task was deleted in ClickUp (404), clears the stale ID and
        recreates the person task so the contact does not get stuck.
        """
        try:
            custom_fields = self._build_person_custom_fields(contact)
            task = await self._client.update_task(
                contact.clickup_task_id,  # type: ignore[arg-type]
                custom_fields=custom_fields,
            )
            if task.url and contact.clickup_task_url != task.url:
                contact.clickup_task_url = task.url
        except ClickUpNotFoundError:
            logger.warning(
                "crm.person_task_gone",
                provider="clickup",
                contact_id=contact.id,
                stale_task_id=contact.clickup_task_id,
            )
            contact.clickup_task_id = None
            contact.clickup_task_url = None
            await self._create_person_task(contact)

    async def _find_existing_person(self, contact: Contact) -> ClickUpTask | None:
        """Deduplicate by email in the person list."""
        if not self._person_email_field_id or not contact.email:
            return None
        return await self._client.find_task_by_custom_field(
            field_id=self._person_email_field_id,
            value=contact.email,
            list_id=self._person_list_id,
        )

    async def _link_person_to_company(
        self, person_task_id: str, company_task_id: str,
    ) -> None:
        """Set relationship fields in both directions (best-effort)."""
        # Person -> Company ("Customer" field)
        if self._contact_relationship_field_id:
            try:
                await self._client.set_custom_field_value(
                    person_task_id,
                    self._contact_relationship_field_id,
                    {"add": [company_task_id], "rem": []},
                )
            except Exception as exc:
                logger.warning(
                    "crm.person_link_failed",
                    direction="person_to_company",
                    person_task_id=person_task_id,
                    company_task_id=company_task_id,
                    error=str(exc),
                )

        # Company -> Person ("Contact and role" field)
        if self._company_contact_field_id:
            try:
                await self._client.set_custom_field_value(
                    company_task_id,
                    self._company_contact_field_id,
                    {"add": [person_task_id], "rem": []},
                )
            except Exception as exc:
                logger.warning(
                    "crm.company_link_failed",
                    direction="company_to_person",
                    person_task_id=person_task_id,
                    company_task_id=company_task_id,
                    error=str(exc),
                )

    def _build_person_custom_fields(self, contact: Contact) -> list[dict[str, Any]]:
        """Build custom fields for a Person task from contact data."""
        fields: list[dict[str, Any]] = []

        field_map: list[tuple[str, str | None]] = [
            (self._person_email_field_id, contact.email),
            (self._person_phone_field_id, contact.phone),
            (self._person_linkedin_field_id, contact.linkedin_url),
            (self._person_role_field_id, contact.title),
        ]
        for field_id, value in field_map:
            if field_id and value:
                fields.append({"id": field_id, "value": value})

        # Split name into surname (first) and lastname (rest)
        if contact.name:
            parts = contact.name.split(" ", 1)
            surname = parts[0]
            lastname = parts[1] if len(parts) > 1 else ""
            if self._person_surname_field_id and surname:
                fields.append({"id": self._person_surname_field_id, "value": surname})
            if self._person_lastname_field_id and lastname:
                fields.append({"id": self._person_lastname_field_id, "value": lastname})

        return fields

    def _build_custom_fields(self, company: Company) -> list[dict[str, Any]]:
        fields: list[dict[str, Any]] = []
        if self._domain_field_id:
            fields.append({"id": self._domain_field_id, "value": company.domain})
        return fields

    def _build_description(
        self, company: Company, contact: Contact | None, signal: Signal | None,
    ) -> str:
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
