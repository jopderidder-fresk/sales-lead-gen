"""ClickUp API v2 client — task creation, update, and search.

Creates and manages lead tasks in ClickUp when companies qualify.
Stores the ClickUp task ID back on the Company record for future updates.

Usage::

    client = ClickUpClient(api_key="pk_...", list_id="12345")
    task = await client.create_task(
        name="Acme Corp",
        custom_fields={"Domain": "acme.com", "Lead Score": 85},
    )
    await client.close()
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.services.api.base_client import BaseAPIClient
from app.services.api.errors import APIError

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ClickUpTask(BaseModel):
    """Minimal representation of a ClickUp task."""

    id: str
    name: str
    status: str | None = None
    url: str | None = None
    custom_fields: list[dict[str, Any]] = Field(default_factory=list)


class ClickUpTaskList(BaseModel):
    """Response from the list-tasks endpoint."""

    tasks: list[ClickUpTask] = Field(default_factory=list)


class ClickUpComment(BaseModel):
    """A comment added to a task."""

    id: str
    comment_text: str = ""


# ---------------------------------------------------------------------------
# ClickUp-specific errors
# ---------------------------------------------------------------------------


class ClickUpRateLimitError(APIError):
    """Raised when ClickUp returns 429 (100 req/min limit)."""

    def __init__(self, message: str = "ClickUp rate limit exceeded") -> None:
        super().__init__(message, provider="clickup", status_code=429)


class ClickUpNotFoundError(APIError):
    """Raised when a task or resource is not found in ClickUp."""

    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            f"ClickUp {resource} not found: {resource_id}",
            provider="clickup",
            status_code=404,
        )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ClickUpClient(BaseAPIClient):
    """ClickUp API v2 provider client for lead task management."""

    provider = "clickup"
    base_url = "https://api.clickup.com/api/v2"

    # ClickUp rate limit: 100 requests/minute.
    rate_limit_capacity: int = 100
    rate_limit_refill: float = 100.0 / 60.0  # ~1.67 tokens/sec

    def __init__(self, api_key: str, *, list_id: str = "") -> None:
        super().__init__(api_key=api_key)
        self.list_id = list_id

    def _build_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": self._api_key,
        }

    def _check_response(self, response: httpx.Response) -> httpx.Response:
        """Extend base check with ClickUp-specific error handling."""
        if response.status_code == 404:
            msg = self._extract_error_message(response)
            raise ClickUpNotFoundError("resource", msg)
        return super()._check_response(response)

    # ------------------------------------------------------------------
    # Task CRUD
    # ------------------------------------------------------------------

    async def create_task(
        self,
        name: str,
        *,
        list_id: str | None = None,
        description: str = "",
        status: str | None = None,
        priority: int | None = None,
        custom_fields: list[dict[str, Any]] | None = None,
    ) -> ClickUpTask:
        """Create a new task in the specified list.

        Args:
            name: Task name / title.
            list_id: ClickUp list ID (falls back to self.list_id).
            description: Markdown description.
            status: Task status name (e.g. "to do").
            priority: 1 (urgent) to 4 (low), or None.
            custom_fields: List of ``{"id": "...", "value": ...}`` dicts.

        Returns:
            The created ``ClickUpTask``.
        """
        target_list = list_id or self.list_id
        if not target_list:
            raise ValueError("list_id is required to create a task")

        body: dict[str, Any] = {"name": name}
        if description:
            body["markdown_description"] = description
        if status is not None:
            body["status"] = status
        if priority is not None:
            body["priority"] = priority
        if custom_fields:
            body["custom_fields"] = custom_fields

        response = await self.post(
            f"/list/{target_list}/task",
            json=body,
            credits_used=1.0,
            cost_estimate=Decimal("0.00"),
        )
        data = response.json()
        return ClickUpTask(
            id=data["id"],
            name=data["name"],
            status=data.get("status", {}).get("status"),
            url=data.get("url"),
            custom_fields=data.get("custom_fields", []),
        )

    async def update_task(
        self,
        task_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: int | None = None,
        custom_fields: list[dict[str, Any]] | None = None,
    ) -> ClickUpTask:
        """Update an existing task's fields.

        Args:
            task_id: The ClickUp task ID.
            name: New task name (optional).
            description: New description (optional).
            status: New status name (optional).
            priority: New priority (optional).
            custom_fields: Updated custom field values (optional).

        Returns:
            The updated ``ClickUpTask``.
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["markdown_description"] = description
        if status is not None:
            body["status"] = status
        if priority is not None:
            body["priority"] = priority
        if custom_fields:
            body["custom_fields"] = custom_fields

        response = await self.put(
            f"/task/{task_id}",
            json=body,
            credits_used=1.0,
            cost_estimate=Decimal("0.00"),
        )
        data = response.json()
        return ClickUpTask(
            id=data["id"],
            name=data["name"],
            status=data.get("status", {}).get("status"),
            url=data.get("url"),
            custom_fields=data.get("custom_fields", []),
        )

    async def get_task(self, task_id: str) -> ClickUpTask:
        """Retrieve a single task by ID.

        Args:
            task_id: The ClickUp task ID.

        Returns:
            ``ClickUpTask`` with current field values.
        """
        response = await self.get(
            f"/task/{task_id}",
            credits_used=1.0,
            cost_estimate=Decimal("0.00"),
        )
        data = response.json()
        return ClickUpTask(
            id=data["id"],
            name=data["name"],
            status=data.get("status", {}).get("status"),
            url=data.get("url"),
            custom_fields=data.get("custom_fields", []),
        )

    async def add_comment(self, task_id: str, comment_text: str) -> ClickUpComment:
        """Add a comment to a task.

        Args:
            task_id: The ClickUp task ID.
            comment_text: Plain-text comment body.

        Returns:
            The created ``ClickUpComment``.
        """
        response = await self.post(
            f"/task/{task_id}/comment",
            json={"comment_text": comment_text},
            credits_used=1.0,
            cost_estimate=Decimal("0.00"),
        )
        data = response.json()
        return ClickUpComment(
            id=str(data.get("id", "")),
            comment_text=comment_text,
        )

    async def set_custom_field_value(
        self,
        task_id: str,
        field_id: str,
        value: Any,
    ) -> None:
        """Set a custom field value on a task (used for relationship fields).

        Args:
            task_id: The ClickUp task ID.
            field_id: The custom field UUID.
            value: The field value. For relationship fields use
                   ``{"add": ["task_id"], "rem": []}``.
        """
        await self.post(
            f"/task/{task_id}/field/{field_id}",
            json={"value": value},
            credits_used=1.0,
            cost_estimate=Decimal("0.00"),
        )

    # ------------------------------------------------------------------
    # Search / find
    # ------------------------------------------------------------------

    async def find_task_by_custom_field(
        self,
        field_id: str,
        value: str,
        *,
        list_id: str | None = None,
    ) -> ClickUpTask | None:
        """Search for a task by a custom field value (e.g. company domain).

        Uses the ClickUp filtered task list endpoint. Returns the first
        matching task or None if no match.

        Args:
            field_id: The custom field UUID to filter on.
            value: The value to match.
            list_id: The list to search in (falls back to self.list_id).

        Returns:
            The matching ``ClickUpTask`` or ``None``.
        """
        target_list = list_id or self.list_id
        if not target_list:
            raise ValueError("list_id is required to search tasks")

        # ClickUp expects custom_fields as a JSON-encoded string in query params
        custom_fields_filter = json.dumps([{"field_id": field_id, "operator": "=", "value": value}])

        response = await self.get(
            f"/list/{target_list}/task",
            params={"custom_fields": custom_fields_filter},
            credits_used=1.0,
            cost_estimate=Decimal("0.00"),
        )
        data = response.json()
        tasks = data.get("tasks", [])
        if not tasks:
            return None

        t = tasks[0]
        return ClickUpTask(
            id=t["id"],
            name=t["name"],
            status=t.get("status", {}).get("status"),
            url=t.get("url"),
            custom_fields=t.get("custom_fields", []),
        )

    async def list_tasks(
        self,
        *,
        list_id: str | None = None,
        page: int = 0,
    ) -> ClickUpTaskList:
        """List tasks in a list (paginated, 100 per page).

        Args:
            list_id: The list to query (falls back to self.list_id).
            page: Zero-based page number.

        Returns:
            ``ClickUpTaskList`` with the current page of tasks.
        """
        target_list = list_id or self.list_id
        if not target_list:
            raise ValueError("list_id is required to list tasks")

        response = await self.get(
            f"/list/{target_list}/task",
            params={"page": str(page)},
            credits_used=1.0,
            cost_estimate=Decimal("0.00"),
        )
        data = response.json()
        tasks = [
            ClickUpTask(
                id=t["id"],
                name=t["name"],
                status=t.get("status", {}).get("status"),
                url=t.get("url"),
                custom_fields=t.get("custom_fields", []),
            )
            for t in data.get("tasks", [])
        ]
        return ClickUpTaskList(tasks=tasks)
