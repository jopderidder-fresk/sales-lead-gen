import ipaddress
import re
from typing import Any
from urllib.parse import urlparse

from rapidfuzz import fuzz
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.company import Company
from app.models.contact import Contact
from app.models.enums import CompanyStatus
from app.models.scrape_job import ScrapeJob
from app.models.signal import Signal
from app.schemas.deduplication import DuplicateGroup, DuplicateGroupMember

logger = get_logger(__name__)

NAME_SIMILARITY_THRESHOLD = 85.0

# Regex: valid public domain with at least one dot and a 2+ char TLD.
_DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)


def normalize_domain(raw: str) -> str:
    """Normalize a domain: strip protocol, www, trailing slashes, lowercase.

    >>> normalize_domain("https://www.Example.com/")
    'example.com'
    >>> normalize_domain("EXAMPLE.COM")
    'example.com'
    """
    value = raw.strip().lower()
    value = urlparse(value).hostname or value if "://" in value else value.split("/")[0]
    # Strip www prefix
    if value.startswith("www."):
        value = value[4:]
    return value.rstrip("/").rstrip(".")


def validate_public_domain(domain: str) -> str | None:
    """Validate that a domain is a legitimate public internet domain.

    Returns an error message if invalid, or None if valid.
    Prevents SSRF by blocking IP addresses, localhost, and internal hostnames.
    """
    normalized = normalize_domain(domain)
    if not normalized:
        return "Domain is empty"

    # Block raw IP addresses (prevents scraping internal/cloud metadata endpoints)
    try:
        addr = ipaddress.ip_address(normalized)
        return f"IP addresses are not allowed as domains: {addr}"
    except ValueError:
        pass  # Not an IP — good

    # Block localhost and common internal hostnames
    blocked = {"localhost", "127.0.0.1", "0.0.0.0", "metadata.google.internal"}
    if normalized in blocked or normalized.endswith(".local") or normalized.endswith(".internal"):
        return f"Internal/reserved domain not allowed: {normalized}"

    # Must look like a real domain (at least one dot, valid TLD)
    if not _DOMAIN_RE.match(normalized):
        return f"Invalid domain format: {normalized}"

    return None


def company_name_similarity(name_a: str, name_b: str) -> float:
    """Return similarity score (0-100) between two company names using token-sort ratio."""
    score: float = fuzz.token_sort_ratio(name_a.lower().strip(), name_b.lower().strip())
    return score


async def is_duplicate_company(session: AsyncSession, name: str, domain: str) -> bool:
    """Check if a company with the same (name, domain) pair already exists."""
    normalized = normalize_domain(domain)

    result = await session.execute(
        select(Company).where(
            Company.name == name,
            Company.domain == normalized,
            Company.status != CompanyStatus.ARCHIVED,
        )
    )
    if result.scalar_one_or_none() is not None:
        return True

    return False


async def find_similar_companies(
    session: AsyncSession, name: str, domain: str
) -> list[dict[str, Any]]:
    """Return potential duplicate companies with similarity scores.

    Each result dict has keys: company_id, name, domain, domain_match, name_similarity.
    """
    normalized = normalize_domain(domain)

    result = await session.execute(select(Company).where(Company.status != CompanyStatus.ARCHIVED))
    companies = result.scalars().all()

    matches: list[dict[str, Any]] = []
    for company in companies:
        domain_match = normalize_domain(company.domain) == normalized
        name_sim = company_name_similarity(name, company.name)

        if domain_match or name_sim >= NAME_SIMILARITY_THRESHOLD:
            matches.append(
                {
                    "company_id": company.id,
                    "name": company.name,
                    "domain": company.domain,
                    "domain_match": domain_match,
                    "name_similarity": round(name_sim, 1),
                }
            )

    # Sort by domain match first, then by name similarity
    matches.sort(key=lambda m: (not m["domain_match"], -m["name_similarity"]))
    return matches


async def is_duplicate_contact(session: AsyncSession, email: str, company_id: int) -> bool:
    """Check if a contact with the same email already exists at the given company."""
    result = await session.execute(
        select(Contact.id).where(
            Contact.email == email.lower().strip(),
            Contact.company_id == company_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def merge_companies(session: AsyncSession, primary_id: int, duplicate_id: int) -> Company:
    """Merge duplicate company into primary: reassign contacts, signals, scrape jobs, then delete.

    This runs inside a single transaction via the session.
    """
    if primary_id == duplicate_id:
        raise ValueError("Cannot merge a company with itself")

    # Verify both companies exist
    primary = (
        await session.execute(select(Company).where(Company.id == primary_id))
    ).scalar_one_or_none()
    duplicate = (
        await session.execute(select(Company).where(Company.id == duplicate_id))
    ).scalar_one_or_none()

    if primary is None:
        raise ValueError(f"Primary company {primary_id} not found")
    if duplicate is None:
        raise ValueError(f"Duplicate company {duplicate_id} not found")

    # Reassign contacts (skip contacts whose email already exists on primary)
    existing_emails_result = await session.execute(
        select(Contact.email).where(
            Contact.company_id == primary_id,
            Contact.email.isnot(None),
        )
    )
    existing_emails = {row[0].lower() for row in existing_emails_result.all() if row[0]}

    dup_contacts = await session.execute(select(Contact).where(Contact.company_id == duplicate_id))
    for contact in dup_contacts.scalars().all():
        if contact.email and contact.email.lower() in existing_emails:
            # Duplicate contact — delete it
            await session.delete(contact)
        else:
            contact.company_id = primary_id
            if contact.email:
                existing_emails.add(contact.email.lower())

    # Reassign signals — skip those with content hashes already on the primary
    existing_hashes_result = await session.execute(
        select(Signal.raw_content_hash).where(
            Signal.company_id == primary_id,
            Signal.raw_content_hash.isnot(None),
        )
    )
    existing_hashes = {row[0] for row in existing_hashes_result.all()}

    dup_signals = await session.execute(select(Signal).where(Signal.company_id == duplicate_id))
    for signal in dup_signals.scalars().all():
        if signal.raw_content_hash and signal.raw_content_hash in existing_hashes:
            await session.delete(signal)
        else:
            signal.company_id = primary_id
            if signal.raw_content_hash:
                existing_hashes.add(signal.raw_content_hash)

    # Reassign scrape jobs
    await session.execute(
        update(ScrapeJob).where(ScrapeJob.company_id == duplicate_id).values(company_id=primary_id)
    )

    # Delete the duplicate company
    await session.execute(delete(Company).where(Company.id == duplicate_id))

    await session.commit()
    await session.refresh(primary)

    logger.info(
        "Companies merged",
        primary_id=primary_id,
        duplicate_id=duplicate_id,
    )
    return primary


async def scan_duplicates(session: AsyncSession) -> list[DuplicateGroup]:
    """Scan all non-archived companies and return groups of potential duplicates.

    Returns a list of duplicate groups, each containing the companies that may be duplicates.

    Phase 1: Group by normalized domain (O(n), catches exact domain duplicates).
    Phase 2: Fuzzy name matching on remaining ungrouped companies (O(n²) but on
             a much smaller set since domain-grouped companies are excluded).
    """
    result = await session.execute(
        select(Company).where(Company.status != CompanyStatus.ARCHIVED).order_by(Company.id)
    )
    companies = list(result.scalars().all())

    grouped: set[int] = set()
    groups: list[DuplicateGroup] = []

    # Phase 1: Group by exact normalized domain (O(n))
    domain_buckets: dict[str, list[Company]] = {}
    for company in companies:
        norm = normalize_domain(company.domain)
        domain_buckets.setdefault(norm, []).append(company)

    for _domain, bucket in domain_buckets.items():
        if len(bucket) < 2:
            continue
        anchor = bucket[0]
        members = [
            DuplicateGroupMember(
                company_id=anchor.id,
                name=anchor.name,
                domain=anchor.domain,
            )
        ]
        for other in bucket[1:]:
            members.append(
                DuplicateGroupMember(
                    company_id=other.id,
                    name=other.name,
                    domain=other.domain,
                    domain_match=True,
                    name_similarity=round(company_name_similarity(anchor.name, other.name), 1),
                )
            )
            grouped.add(other.id)
        grouped.add(anchor.id)
        groups.append(DuplicateGroup(companies=members))

    # Phase 2: Fuzzy name matching on remaining ungrouped companies
    remaining = [c for c in companies if c.id not in grouped]

    for i, company_a in enumerate(remaining):
        if company_a.id in grouped:
            continue

        members = [
            DuplicateGroupMember(
                company_id=company_a.id,
                name=company_a.name,
                domain=company_a.domain,
            )
        ]

        for company_b in remaining[i + 1 :]:
            if company_b.id in grouped:
                continue

            name_sim = company_name_similarity(company_a.name, company_b.name)
            if name_sim >= NAME_SIMILARITY_THRESHOLD:
                members.append(
                    DuplicateGroupMember(
                        company_id=company_b.id,
                        name=company_b.name,
                        domain=company_b.domain,
                        domain_match=False,
                        name_similarity=round(name_sim, 1),
                    )
                )
                grouped.add(company_b.id)

        if len(members) > 1:
            grouped.add(company_a.id)
            groups.append(DuplicateGroup(companies=members))

    logger.info("Duplicate scan completed", groups_found=len(groups))
    return groups
