"""Pick news- and vacancy-related URLs from a domain crawl / map listing.

Sites use different paths (`/nieuws/`, `/blog/`, `/careers`, Greenhouse boards, etc.).
We classify URLs by path segments (and a few well-known hiring path patterns) and
skip generic marketing pages unless they live under a news/jobs branch.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Path fragments (matched as /segment/ or end-of-path). Lowercase.
_NEWS_FRAGMENTS: frozenset[str] = frozenset(
    {
        "news",
        "nieuws",
        "blog",
        "blogs",
        "press",
        "pers",
        "media",
        "magazine",
        "stories",
        "story",
        "article",
        "articles",
        "insights",
        "updates",
        "announcements",
        "releases",
        "changelog",
        "release-notes",
        "events",
        "evenementen",
        "persbericht",
        "aktuelles",
        "nachrichten",
    }
)

_JOBS_FRAGMENTS: frozenset[str] = frozenset(
    {
        "career",
        "careers",
        "jobs",
        "job",
        "vacancy",
        "vacancies",
        "vacatures",
        "vacature",
        "werken-bij",
        "werkenbij",
        "werk-bij",
        "join-us",
        "joinus",
        "join-our-team",
        "hiring",
        "recruitment",
        "recruit",
        "openings",
        "open-positions",
        "positions",
        "stellenangebote",
        "stellenangebot",
        "karriere",
        "employment",
    }
)

# Strong skips — marketing / legal / auth / assets (substring in normalized path).
_EXCLUDE_SUBSTRINGS: frozenset[str] = frozenset(
    {
        "/login",
        "/signin",
        "/signup",
        "/register",
        "/auth/",
        "/account",
        "/cart",
        "/checkout",
        "/privacy",
        "/terms",
        "/cookie",
        "/disclaimer",
        "/wp-admin",
        "/wp-content",
        "/wp-includes",
        "/admin",
        "/cdn/",
        "/assets/",
        "/static/",
        "/fonts/",
        "/images/",
        "/img/",
        "/favicon",
    }
)

_EXCLUDE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".svg",
        ".ico",
        ".zip",
        ".mp4",
        ".mp3",
        ".xml",
        ".rss",
        ".atom",
    }
)

# Standalone segments that are almost never intel signal pages.
_BARE_MARKETING_SEGMENTS: frozenset[str] = frozenset(
    {
        "about",
        "about-us",
        "over-ons",
        "contact",
        "pricing",
        "product",
        "products",
        "services",
        "solutions",
        "home",
        "team",
        "leadership",
        "customers",
        "clients",
        "faq",
        "support",
        "documentation",
        "docs",
    }
)

_SLUG_SEGMENT = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", re.IGNORECASE)


def _normalize_host(hostname: str | None) -> str:
    if not hostname:
        return ""
    h = hostname.lower()
    if h.startswith("www."):
        h = h[4:]
    return h


def url_matches_domain(url: str, domain: str) -> bool:
    """True if URL host equals ``domain`` (ignoring leading ``www.``)."""
    host = _normalize_host(urlparse(url).hostname)
    return bool(host and host == domain.lower().strip())


def _normalized_path(path: str) -> str:
    """`/foo/bar/` style lowercased path for safe substring checks."""
    p = (path or "/").lower().strip()
    if not p.startswith("/"):
        p = "/" + p
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    if p == "/":
        return "/"
    return p + "/"


def _path_segments(norm_path: str) -> list[str]:
    return [s for s in norm_path.strip("/").split("/") if s]


def _segment_matches_segment(s: str, fragments: frozenset[str]) -> bool:
    """Path segment equals a fragment or a compound like ``vacatures-amsterdam``."""
    sl = s.lower()
    for frag in fragments:
        if sl == frag or sl.startswith(frag + "-") or sl.startswith(frag + "_"):
            return True
    return False


def _fragment_hit(norm_path: str, fragments: frozenset[str]) -> bool:
    """True if a fragment appears as its own segment or as a compound segment prefix."""
    for frag in fragments:
        needle = f"/{frag}/"
        if needle in norm_path or norm_path.startswith(f"/{frag}/") or norm_path == f"/{frag}/":
            return True
    for seg in _path_segments(norm_path):
        if _segment_matches_segment(seg, fragments):
            return True
    return False


def classify_url(url: str) -> str | None:
    """Return ``news``, ``jobs``, or ``None`` if URL should not be scraped for intel."""
    parsed = urlparse(url)
    path = parsed.path or "/"
    norm = _normalized_path(path)
    path_l = path.lower()

    if any(path_l.endswith(ext) for ext in _EXCLUDE_EXTENSIONS):
        return None

    for ex in _EXCLUDE_SUBSTRINGS:
        if ex in norm:
            return None

    is_jobs = _fragment_hit(norm, _JOBS_FRAGMENTS)
    is_news = _fragment_hit(norm, _NEWS_FRAGMENTS)

    if is_jobs:
        return "jobs"
    if is_news:
        return "news"

    segments = [s for s in path.strip("/").split("/") if s]
    if len(segments) == 1:
        seg = segments[0].lower()
        if seg in _BARE_MARKETING_SEGMENTS:
            return None

    if len(segments) >= 2:
        parent = segments[-2].lower()
        leaf = segments[-1].lower()
        if parent in _NEWS_FRAGMENTS | _JOBS_FRAGMENTS:
            if _SLUG_SEGMENT.match(leaf) or leaf.isdigit():
                return "news" if parent in _NEWS_FRAGMENTS else "jobs"

    return None


def select_intel_urls(
    links: list[str],
    domain: str,
    *,
    max_news: int = 14,
    max_jobs: int = 10,
    max_total: int = 22,
) -> tuple[list[str], dict[str, int]]:
    """Filter ``links`` to news/jobs URLs for ``domain``. Returns (urls, stats).

    Ordering: jobs first (open roles are high signal), then news; URLs are
    de-duplicated while preserving first-seen order within each bucket.
    """
    stats = {"jobs": 0, "news": 0, "skipped": 0, "out_of_domain": 0}
    jobs: list[str] = []
    news: list[str] = []
    seen: set[str] = set()
    dom = domain.lower().strip()

    for raw in links:
        raw = (raw or "").strip()
        if not raw:
            continue
        if not url_matches_domain(raw, dom):
            stats["out_of_domain"] += 1
            continue
        kind = classify_url(raw)
        if kind is None:
            stats["skipped"] += 1
            continue
        if raw in seen:
            continue
        seen.add(raw)
        if kind == "jobs":
            jobs.append(raw)
        else:
            news.append(raw)

    jobs = jobs[:max_jobs]
    news = news[:max_news]

    merged: list[str] = []
    for u in jobs + news:
        if len(merged) >= max_total:
            break
        if u not in merged:
            merged.append(u)

    stats["jobs"] = sum(1 for u in merged if classify_url(u) == "jobs")
    stats["news"] = sum(1 for u in merged if classify_url(u) == "news")
    return merged, stats


def fallback_intel_paths() -> list[str]:
    """Short path list when map returns nothing useful (common CMS patterns)."""
    return [
        "/careers",
        "/jobs",
        "/vacatures",
        "/vacature",
        "/werken-bij",
        "/news",
        "/nieuws",
        "/blog",
        "/press",
    ]
