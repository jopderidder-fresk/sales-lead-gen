from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class SizeFilter(BaseModel):
    min_employees: int | None = Field(default=None, ge=0)
    max_employees: int | None = Field(default=None, ge=0)
    min_revenue: float | None = Field(default=None, ge=0)
    max_revenue: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "SizeFilter":
        if (
            self.min_employees is not None
            and self.max_employees is not None
            and self.min_employees >= self.max_employees
        ):
            msg = "min_employees must be less than max_employees"
            raise ValueError(msg)
        if (
            self.min_revenue is not None
            and self.max_revenue is not None
            and self.min_revenue >= self.max_revenue
        ):
            msg = "min_revenue must be less than max_revenue"
            raise ValueError(msg)
        return self


class GeoFilter(BaseModel):
    countries: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)


class NegativeFilters(BaseModel):
    excluded_industries: list[str] = Field(default_factory=list)
    excluded_domains: list[str] = Field(default_factory=list)


class ICPProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    industry_filter: list[str] | None = None
    size_filter: SizeFilter | None = None
    geo_filter: GeoFilter | None = None
    tech_filter: list[str] | None = None
    negative_filters: NegativeFilters | None = None

    @model_validator(mode="after")
    def require_at_least_one_positive_filter(self) -> "ICPProfileCreate":
        has_industry = bool(self.industry_filter)
        has_size = self.size_filter is not None and any(
            v is not None
            for v in [
                self.size_filter.min_employees,
                self.size_filter.max_employees,
                self.size_filter.min_revenue,
                self.size_filter.max_revenue,
            ]
        )
        has_geo = self.geo_filter is not None and any(
            bool(v)
            for v in [
                self.geo_filter.countries,
                self.geo_filter.regions,
                self.geo_filter.cities,
            ]
        )
        has_tech = bool(self.tech_filter)

        if not any([has_industry, has_size, has_geo, has_tech]):
            msg = "At least one positive filter (industry, size, geo, or tech) is required"
            raise ValueError(msg)
        return self


class ICPProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    industry_filter: list[str] | None = None
    size_filter: SizeFilter | None = None
    geo_filter: GeoFilter | None = None
    tech_filter: list[str] | None = None
    negative_filters: NegativeFilters | None = None

    @model_validator(mode="after")
    def require_at_least_one_positive_filter_if_clearing(self) -> "ICPProfileUpdate":
        """Prevent clearing all positive filters via an update."""
        # Only validate if at least one positive filter field was explicitly set
        positive_fields = {"industry_filter", "size_filter", "geo_filter", "tech_filter"}
        set_fields = self.model_fields_set
        if not (positive_fields & set_fields):
            return self  # No positive filter fields were changed

        has_industry = bool(self.industry_filter)
        has_size = self.size_filter is not None and any(
            v is not None
            for v in [
                self.size_filter.min_employees,
                self.size_filter.max_employees,
                self.size_filter.min_revenue,
                self.size_filter.max_revenue,
            ]
        )
        has_geo = self.geo_filter is not None and any(
            bool(v)
            for v in [
                self.geo_filter.countries,
                self.geo_filter.regions,
                self.geo_filter.cities,
            ]
        )
        has_tech = bool(self.tech_filter)

        # If all provided positive filters are empty/None, reject
        all_provided_empty = all(
            not {"industry_filter": has_industry, "size_filter": has_size,
                 "geo_filter": has_geo, "tech_filter": has_tech}.get(f, True)
            for f in (positive_fields & set_fields)
        )
        if all_provided_empty and len(positive_fields & set_fields) == len(positive_fields):
            msg = "At least one positive filter (industry, size, geo, or tech) is required"
            raise ValueError(msg)
        return self


class ICPProfileResponse(BaseModel):
    id: int
    name: str
    industry_filter: list[str] | None = None
    size_filter: SizeFilter | None = None
    geo_filter: GeoFilter | None = None
    tech_filter: list[str] | None = None
    negative_filters: NegativeFilters | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
