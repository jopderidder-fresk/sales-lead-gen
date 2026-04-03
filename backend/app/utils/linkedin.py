"""LinkedIn URL extraction and validation utilities."""

from __future__ import annotations

import re

_LINKEDIN_COMPANY_RE = re.compile(
    r'https?://(?:www\.)?linkedin\.com/company/([a-zA-Z0-9_-]+)',
)


def extract_linkedin_company_url(markdown: str) -> str | None:
    """Extract and normalize a LinkedIn company URL from page content.

    Returns the first match as ``https://www.linkedin.com/company/{slug}``
    or ``None`` if no company URL is found.
    """
    match = _LINKEDIN_COMPANY_RE.search(markdown)
    if not match:
        return None
    slug = match.group(1)
    # Ignore generic slugs that are clearly not real company pages
    if slug.lower() in {"company", "companies", "signup", "login"}:
        return None
    return f"https://www.linkedin.com/company/{slug}"


def is_valid_linkedin_company_url(url: str) -> bool:
    """Check whether *url* looks like a LinkedIn company page."""
    return bool(_LINKEDIN_COMPANY_RE.match(url))
