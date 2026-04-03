"""CRM provider protocol — abstract interface for task management integrations.

Any CRM integration (ClickUp, HubSpot, Salesforce, etc.) implements this
protocol so the rest of the system can work with any provider generically.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


class CRMTask(BaseModel):
    """Generic representation of a task in an external CRM system."""

    id: str
    name: str
    status: str | None = None
    url: str | None = None
    provider: str


class CRMSyncResult(BaseModel):
    """Result of a bulk sync operation."""

    created: list[tuple[int, str]] = []  # (company_id, task_id)
    updated: list[tuple[int, str]] = []
    skipped: list[int] = []
    errors: list[tuple[int, str]] = []  # (company_id, error_message)

    def summary(self) -> str:
        parts = [
            f"created={len(self.created)}",
            f"updated={len(self.updated)}",
            f"skipped={len(self.skipped)}",
            f"errors={len(self.errors)}",
        ]
        return f"CRM sync: {', '.join(parts)}"


class CRMProvider(Protocol):
    """Protocol that all CRM integrations must satisfy."""

    @property
    def provider_name(self) -> str: ...

    async def push_company(self, session: AsyncSession, company_id: int) -> CRMTask:
        """Create or update a task for a company in the CRM."""
        ...

    async def sync_status(self, session: AsyncSession, company_id: int) -> CRMTask | None:
        """Fetch the task from the CRM and sync its status to the local DB."""
        ...

    async def get_task(self, session: AsyncSession, company_id: int) -> CRMTask | None:
        """Retrieve the CRM task linked to a company (without syncing)."""
        ...

    async def sync_qualified_companies(self, session: AsyncSession) -> CRMSyncResult:
        """Batch sync all qualifying companies to the CRM."""
        ...

    async def close(self) -> None:
        """Clean up resources (HTTP clients, etc.)."""
        ...
