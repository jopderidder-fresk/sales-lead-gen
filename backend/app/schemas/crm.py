"""CRM integration schemas — generic response types for any CRM provider."""

from datetime import datetime

from pydantic import BaseModel, Field


class CRMIntegrationResponse(BaseModel):
    """CRM integration linked to a company."""

    provider: str
    external_id: str
    external_url: str | None = None
    external_status: str | None = None
    synced_at: datetime | None = None

    model_config = {"from_attributes": True}


class CRMPushResponse(BaseModel):
    """Response from pushing a company to the CRM."""

    company_id: int
    task_id: str | None = None
    task_url: str | None = None
    provider: str
    message: str


class CRMTaskResponse(BaseModel):
    """CRM task details retrieved from the external system."""

    id: str
    name: str
    status: str | None = None
    url: str | None = None
    provider: str


class CRMSyncResponse(BaseModel):
    """Response from triggering a bulk CRM sync."""

    task_id: str
    message: str


# ── CRM settings ──────────────────────────────────────────────────


class ClickUpCRMSettings(BaseModel):
    """ClickUp-specific fields returned inside the CRM settings response."""

    api_key_set: bool
    api_key_preview: str | None = None
    workspace_id: str = ""
    space_id: str = ""
    folder_id: str = ""
    list_id: str = ""
    domain_field_id: str = ""
    # Person task settings
    person_list_id: str = ""
    person_email_field_id: str = ""
    person_phone_field_id: str = ""
    person_linkedin_field_id: str = ""
    person_surname_field_id: str = ""
    person_lastname_field_id: str = ""
    person_role_field_id: str = ""
    contact_relationship_field_id: str = ""
    company_contact_field_id: str = ""


class CRMSettingsResponse(BaseModel):
    """Full CRM settings payload."""

    provider: str  # "clickup" or "" (none)
    configured: bool
    available_providers: list[str] = Field(default_factory=lambda: ["clickup"])
    clickup: ClickUpCRMSettings | None = None


class CRMSettingsUpdate(BaseModel):
    """Payload for updating CRM settings."""

    provider: str | None = None
    # ClickUp fields — only required when provider is "clickup"
    clickup_api_key: str | None = None
    clickup_workspace_id: str | None = None
    clickup_space_id: str | None = None
    clickup_folder_id: str | None = None
    clickup_list_id: str | None = None
    clickup_domain_field_id: str | None = None
    # Person task fields
    clickup_person_list_id: str | None = None
    clickup_person_email_field_id: str | None = None
    clickup_person_phone_field_id: str | None = None
    clickup_person_linkedin_field_id: str | None = None
    clickup_person_surname_field_id: str | None = None
    clickup_person_lastname_field_id: str | None = None
    clickup_person_role_field_id: str | None = None
    clickup_contact_relationship_field_id: str | None = None
    clickup_company_contact_field_id: str | None = None
