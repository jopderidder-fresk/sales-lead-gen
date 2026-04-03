from pydantic import BaseModel, Field


class ClickUpSettingsResponse(BaseModel):
    """Current ClickUp integration settings (read-only view)."""

    configured: bool = Field(description="Whether the ClickUp API key is set")
    workspace_id: str
    space_id: str
    folder_id: str
    list_id: str


class ClickUpSettingsUpdate(BaseModel):
    """Updatable ClickUp workspace mapping settings."""

    workspace_id: str | None = Field(default=None, max_length=100)
    space_id: str | None = Field(default=None, max_length=100)
    folder_id: str | None = Field(default=None, max_length=100)
    list_id: str | None = Field(default=None, max_length=100)


class ClickUpPushResponse(BaseModel):
    """Response from pushing a company to ClickUp."""

    company_id: int
    task_id: str | None = None
    task_url: str | None = None
    message: str


class ClickUpSyncResponse(BaseModel):
    """Response from triggering a bulk ClickUp sync."""

    task_id: str
    message: str


class ClickUpTaskResponse(BaseModel):
    """ClickUp task linked to a company."""

    id: str
    name: str
    status: str | None = None
    url: str | None = None
