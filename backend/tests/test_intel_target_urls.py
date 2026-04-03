"""Tests for news/jobs URL heuristics used in monitoring and scrape tasks."""

from app.services.intel_target_urls import (
    classify_url,
    select_intel_urls,
    url_matches_domain,
)


def test_classify_blog_and_careers() -> None:
    assert classify_url("https://acme.com/blog/2024/hello") == "news"
    assert classify_url("https://acme.com/en/careers") == "jobs"
    assert classify_url("https://acme.com/nieuws/lancering") == "news"


def test_classify_compound_vacatures_segment() -> None:
    assert classify_url("https://x.nl/vacatures-amsterdam") == "jobs"


def test_classify_skips_about_and_privacy() -> None:
    assert classify_url("https://acme.com/about") is None
    assert classify_url("https://acme.com/en/privacy-policy") is None
    assert classify_url("https://acme.com/static/logo.png") is None


def test_url_matches_domain_ignores_www() -> None:
    assert url_matches_domain("https://www.acme.com/jobs", "acme.com")
    assert not url_matches_domain("https://other.com/jobs", "acme.com")


def test_select_intel_urls_filters_domain_and_buckets() -> None:
    links = [
        "https://acme.com/about",
        "https://acme.com/blog/post-one",
        "https://acme.com/careers",
        "https://evil.com/careers",
    ]
    urls, stats = select_intel_urls(links, "acme.com")
    assert "https://acme.com/blog/post-one" in urls
    assert "https://acme.com/careers" in urls
    assert "https://acme.com/about" not in urls
    assert stats["out_of_domain"] == 1
    assert stats["skipped"] >= 1


def test_jobs_order_before_news_in_merge() -> None:
    links = [
        "https://co.example/nieuws/a",
        "https://co.example/careers",
    ]
    urls, _ = select_intel_urls(links, "co.example", max_total=10)
    assert urls[0].endswith("/careers")
