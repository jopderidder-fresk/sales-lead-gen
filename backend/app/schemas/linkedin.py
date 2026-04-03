"""LinkedIn scraping settings schemas."""

from pydantic import BaseModel, Field


class LinkedInSettingsResponse(BaseModel):
    """Current LinkedIn scraping configuration."""

    enabled: bool = Field(description="Whether the scrape-linkedin-batch job is enabled")
    interval_days: int = Field(description="Run batch scrape every N days")
    days_back: int = Field(description="Scrape LinkedIn posts from the last N days")
    last_batch_run: str | None = Field(
        default=None,
        description="ISO timestamp of last successful batch run",
    )


class LinkedInSettingsUpdate(BaseModel):
    """Updatable LinkedIn scraping settings."""

    enabled: bool | None = Field(default=None)
    interval_days: int | None = Field(default=None, ge=1, le=30)
    days_back: int | None = Field(default=None, ge=1, le=90)
