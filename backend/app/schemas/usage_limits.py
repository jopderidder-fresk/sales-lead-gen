from pydantic import BaseModel, Field


class UsageLimitsResponse(BaseModel):
    max_companies_per_discovery_run: int
    max_discovery_runs_per_day: int
    max_enrichments_per_day: int
    max_scrapes_per_day: int
    max_monitoring_companies_per_run: int
    daily_api_cost_limit: float

    # Today's usage (read-only counters)
    discovery_runs_today: int = 0
    enrichments_today: int = 0
    scrapes_today: int = 0
    api_cost_today: float = 0.0


class UsageLimitsUpdate(BaseModel):
    max_companies_per_discovery_run: int | None = Field(default=None, ge=1, le=1000)
    max_discovery_runs_per_day: int | None = Field(default=None, ge=1, le=100)
    max_enrichments_per_day: int | None = Field(default=None, ge=1, le=10000)
    max_scrapes_per_day: int | None = Field(default=None, ge=1, le=10000)
    max_monitoring_companies_per_run: int | None = Field(default=None, ge=1, le=10000)
    daily_api_cost_limit: float | None = Field(default=None, ge=0.0)
