"""Company Discovery Engine — discovers new companies from ICP profile.

Queries Bedrijfsdata, deduplicates results against the existing database,
and stores new companies with status "discovered".

Usage::

    service = DiscoveryService(
        bedrijfsdata_api_key="bd-...",
    )
    result = await service.run(session)
    await service.close()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.company import Company
from app.models.enums import CompanyStatus
from app.models.icp_profile import ICPProfile
from app.services.api.bedrijfsdata import (
    BedrijfsdataClient,
    BedrijfsdataCompany,
)
from app.services.deduplication import (
    company_name_similarity,
    normalize_domain,
)

logger = get_logger(__name__)

NAME_SIMILARITY_THRESHOLD = 85.0
MAX_RUNTIME_SECONDS = 30 * 60  # 30 minutes


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------


@dataclass
class DiscoveryResult:
    """Tracks the outcome of a discovery run."""

    companies_found: int = 0
    companies_added: int = 0
    companies_skipped: int = 0
    firecrawl_found: int = 0
    bedrijfsdata_found: int = 0
    elapsed_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"found={self.companies_found} added={self.companies_added} "
            f"skipped={self.companies_skipped} "
            f"firecrawl={self.firecrawl_found} bedrijfsdata={self.bedrijfsdata_found} "
            f"elapsed={self.elapsed_seconds:.1f}s errors={len(self.errors)}"
        )


# ---------------------------------------------------------------------------
# ICP → query translation
# ---------------------------------------------------------------------------


def calculate_icp_score(
    profile: ICPProfile,
    *,
    industry: str | None = None,
    employees: int | None = None,
    location: str | None = None,
    techs: list[str] | None = None,
) -> float:
    """Calculate ICP match score as (matching criteria / total criteria) * 100."""
    total_criteria = 0
    matching_criteria = 0

    # Industry match
    industries: list[str] | None = profile.industry_filter
    if industries:
        total_criteria += 1
        if industry:
            industry_lower = industry.lower()
            if any(ind.lower() in industry_lower or industry_lower in ind.lower() for ind in industries):
                matching_criteria += 1

    # Size match
    size: dict[str, Any] | None = profile.size_filter
    if size and (size.get("min_employees") is not None or size.get("max_employees") is not None):
        total_criteria += 1
        if employees is not None:
            min_emp = size.get("min_employees")
            max_emp = size.get("max_employees")
            if (min_emp is None or employees >= min_emp) and (max_emp is None or employees <= max_emp):
                matching_criteria += 1

    # Geography match
    geo: dict[str, Any] | None = profile.geo_filter
    if geo:
        all_locations = (
            [c.lower() for c in geo.get("countries", [])]
            + [r.lower() for r in geo.get("regions", [])]
            + [c.lower() for c in geo.get("cities", [])]
        )
        if all_locations:
            total_criteria += 1
            if location and any(loc in location.lower() for loc in all_locations):
                matching_criteria += 1

    # Tech match
    tech_filter: list[str] | None = profile.tech_filter
    if tech_filter:
        total_criteria += 1
        if techs:
            techs_lower = {t.lower() for t in techs}
            if any(tf.lower() in techs_lower for tf in tech_filter):
                matching_criteria += 1

    if total_criteria == 0:
        return 50.0  # no criteria to match against

    return round((matching_criteria / total_criteria) * 100, 1)


# ---------------------------------------------------------------------------
# Discovery Service
# ---------------------------------------------------------------------------


class DiscoveryService:
    """Orchestrates company discovery from Bedrijfsdata."""

    def __init__(
        self,
        bedrijfsdata_api_key: str,
        max_companies: int = 0,
    ) -> None:
        self._bedrijfsdata = BedrijfsdataClient(api_key=bedrijfsdata_api_key)
        self._max_companies = max_companies  # 0 = unlimited

    async def close(self) -> None:
        await self._bedrijfsdata.close()

    async def run(self, session: AsyncSession) -> DiscoveryResult:
        """Execute a full discovery run using the active ICP profile."""
        start = time.monotonic()
        result = DiscoveryResult()

        # 1. Load active ICP profile
        profile = await self._get_active_profile(session)
        if profile is None:
            result.errors.append("No active ICP profile found")
            result.elapsed_seconds = time.monotonic() - start
            logger.warning("discovery.no_active_icp")
            return result

        logger.info("discovery.start", icp_profile=profile.name)

        # 2. Query Bedrijfsdata
        try:
            bedrijfsdata_companies = await self._search_bedrijfsdata(profile, result)
        except Exception as exc:
            error_msg = f"Bedrijfsdata search failed: {exc}"
            result.errors.append(error_msg)
            logger.error("discovery.bedrijfsdata_error", error=str(exc))
            bedrijfsdata_companies = []

        # 3. Pre-load existing companies for dedup (single query)
        existing_pairs, existing_names = await self._load_existing_companies(session)

        # 4. Deduplicate and store
        await self._process_bedrijfsdata_results(
            session, profile, bedrijfsdata_companies, result, start,
            existing_pairs, existing_names,
        )

        result.elapsed_seconds = time.monotonic() - start
        logger.info("discovery.complete", **{"result": result.summary()})
        return result

    # ------------------------------------------------------------------
    # Internal: query sources
    # ------------------------------------------------------------------

    async def _search_bedrijfsdata(
        self, profile: ICPProfile, result: DiscoveryResult
    ) -> list[BedrijfsdataCompany]:
        """Search via Bedrijfsdata using structured ICP filters."""
        params = BedrijfsdataClient.icp_to_search_params(
            industry_filter=profile.industry_filter,
            size_filter=profile.size_filter,
            geo_filter=profile.geo_filter,
            tech_filter=profile.tech_filter,
            rows=50,
        )
        logger.info("discovery.bedrijfsdata_search", param_keys=list(params.keys()))

        search_response = await self._bedrijfsdata.search_companies(params)
        result.bedrijfsdata_found = len(search_response.companies)
        logger.info("discovery.bedrijfsdata_found", count=len(search_response.companies))
        return search_response.companies

    # ------------------------------------------------------------------
    # Internal: deduplication and storage
    # ------------------------------------------------------------------

    @staticmethod
    async def _load_existing_companies(
        session: AsyncSession,
    ) -> tuple[set[tuple[str, str]], list[str]]:
        """Load existing (name, domain) pairs and names once for dedup checks."""
        result = await session.execute(
            select(Company.domain, Company.name).where(
                Company.status != CompanyStatus.ARCHIVED
            )
        )
        rows = result.all()
        pairs = {(r.name, r.domain) for r in rows if r.domain}
        names = [r.name for r in rows]
        return pairs, names

    def _is_duplicate(
        self,
        name: str,
        domain: str | None,
        existing_pairs: set[tuple[str, str]],
        existing_names: list[str],
        kvk_number: str | None = None,
    ) -> bool:
        """Check if a company already exists by (name, domain) pair or name similarity."""
        if domain:
            normalized = normalize_domain(domain)
            if (name, normalized) in existing_pairs:
                return True

        # Fuzzy name match (catches renamed entities with identical business)
        for existing_name in existing_names:
            if company_name_similarity(name, existing_name) >= NAME_SIMILARITY_THRESHOLD:
                return True

        return False

    def _cap_reached(self, result: DiscoveryResult) -> bool:
        """Check if the per-run company addition cap has been reached."""
        return self._max_companies > 0 and result.companies_added >= self._max_companies

    async def _process_bedrijfsdata_results(
        self,
        session: AsyncSession,
        profile: ICPProfile,
        companies: list[BedrijfsdataCompany],
        result: DiscoveryResult,
        start: float,
        existing_pairs: set[tuple[str, str]],
        existing_names: list[str],
    ) -> None:
        """Deduplicate and store companies from Bedrijfsdata."""
        for bd_company in companies:
            if self._is_timed_out(start):
                result.errors.append("Runtime limit reached during Bedrijfsdata processing")
                break
            if self._cap_reached(result):
                logger.info("discovery.cap_reached", cap=self._max_companies)
                break

            result.companies_found += 1

            domain = bd_company.domain
            if not domain:
                result.companies_skipped += 1
                continue

            if self._is_duplicate(
                bd_company.name, domain, existing_pairs, existing_names,
                kvk_number=bd_company.coc,
            ):
                result.companies_skipped += 1
                continue

            # Build location string
            location_parts = [p for p in [bd_company.city, bd_company.province] if p]
            location = ", ".join(location_parts) if location_parts else None

            # Build size string
            size = f"{bd_company.employees} employees" if bd_company.employees else None

            # Industry from labels or first SBI code description
            industry = bd_company.industry_labels[0] if bd_company.industry_labels else None

            icp_score = calculate_icp_score(
                profile,
                industry=industry,
                employees=bd_company.employees,
                location=location,
                techs=bd_company.apps if bd_company.apps else None,
            )

            normalized = normalize_domain(domain)

            # Collect supplementary data for the bedrijfsdata JSONB
            bd_meta: dict[str, object] = {}
            if bd_company.id is not None:
                bd_meta["bedrijfsdata_id"] = bd_company.id
            if bd_company.sbi_codes:
                bd_meta["sbi_codes"] = ",".join(bd_company.sbi_codes)
            if bd_company.apps:
                bd_meta["apps"] = ",".join(bd_company.apps)
            if bd_company.latitude is not None and bd_company.longitude is not None:
                bd_meta["coordinaten"] = f"{bd_company.latitude},{bd_company.longitude}"

            # Build website_url from domain if available
            website_url = f"https://{bd_company.domain}" if bd_company.domain else None

            new_company = Company(
                name=bd_company.name,
                domain=normalized,
                industry=industry,
                size=size,
                location=location,
                status=CompanyStatus.DISCOVERED,
                icp_score=icp_score,
                kvk_number=bd_company.coc,
                phone=bd_company.phone,
                email=bd_company.email,
                website_url=website_url,
                address=bd_company.address,
                postal_code=bd_company.postal_code,
                city=bd_company.city,
                province=bd_company.province,
                country="NL",
                founded_year=bd_company.founded,
                employee_count=bd_company.employees,
                organization_type=bd_company.orgtype,
                linkedin_url=bd_company.linkedin_url,
                facebook_url=bd_company.facebook_url,
                twitter_url=bd_company.twitter_url,
                bedrijfsdata=bd_meta if bd_meta else None,
            )
            try:
                async with session.begin_nested():
                    session.add(new_company)
                    await session.flush()
                result.companies_added += 1
                existing_pairs.add((bd_company.name, normalized))
                existing_names.append(bd_company.name)
            except Exception:
                result.companies_skipped += 1
                logger.warning(
                    "discovery.store_failed",
                    company_name=bd_company.name,
                    domain=domain,
                )

        await session.commit()

    # ------------------------------------------------------------------
    # Internal: helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_active_profile(session: AsyncSession) -> ICPProfile | None:
        result = await session.execute(
            select(ICPProfile).where(ICPProfile.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _is_timed_out(start: float) -> bool:
        return (time.monotonic() - start) >= MAX_RUNTIME_SECONDS
