from pydantic import BaseModel, Field


class SlackSettingsResponse(BaseModel):
    """Current Slack integration settings (read-only view)."""

    configured: bool = Field(description="Whether any Slack webhook URL is set")
    webhook_url_set: bool = Field(description="Whether the primary webhook URL is configured")
    digest_webhook_url_set: bool = Field(description="Whether the digest webhook URL is configured")
    digest_hour: int = Field(description="Hour (UTC) for daily digest delivery")
    weekly_day: int = Field(description="Day of week for weekly summary (0=Monday)")
    webhook_url_preview: str | None = Field(
        default=None,
        description="First 34 chars of the primary webhook URL followed by **** (or None if not set)",
    )
    digest_webhook_url_preview: str | None = Field(
        default=None,
        description="First 34 chars of the digest webhook URL followed by **** (or None if not set)",
    )


class SlackSettingsUpdate(BaseModel):
    """Updatable Slack notification settings."""

    webhook_url: str | None = Field(default=None, max_length=500)
    digest_webhook_url: str | None = Field(default=None, max_length=500)
    digest_hour: int | None = Field(default=None, ge=0, le=23)
    weekly_day: int | None = Field(default=None, ge=0, le=6)


class SlackTestResponse(BaseModel):
    """Response from sending a test Slack notification."""

    success: bool
    message: str


class SlackDigestResponse(BaseModel):
    """Response from triggering a manual digest."""

    task_id: str
    message: str
