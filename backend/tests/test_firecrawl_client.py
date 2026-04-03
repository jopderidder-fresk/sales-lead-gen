"""Tests for the Firecrawl API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from app.services.api.errors import AuthenticationError, ProviderUnavailableError
from app.services.api.firecrawl import (
    CrawlPage,
    CrawlResponse,
    CrawlStatus,
    FirecrawlClient,
    FirecrawlCrawlFailedError,
    FirecrawlCreditsExhaustedError,
    FirecrawlScrapeFailedError,
    ScrapeResponse,
    SearchResponse,
    SearchResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> FirecrawlClient:
    return FirecrawlClient(api_key="fc-test-key")


def _mock_response(status_code: int = 200, json_data: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_data or {},
        request=httpx.Request("POST", "https://api.firecrawl.dev/v1/test"),
    )


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestSearchResult:
    def test_minimal(self) -> None:
        r = SearchResult(url="https://example.com")
        assert r.url == "https://example.com"
        assert r.title is None
        assert r.markdown is None

    def test_full(self) -> None:
        r = SearchResult(url="https://example.com", title="Example", markdown="# Hello")
        assert r.title == "Example"
        assert r.markdown == "# Hello"


class TestCrawlPage:
    def test_defaults(self) -> None:
        p = CrawlPage(url="https://example.com/page")
        assert p.markdown == ""
        assert p.title is None
        assert p.status_code is None


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestFirecrawlErrors:
    def test_credits_exhausted_error(self) -> None:
        err = FirecrawlCreditsExhaustedError()
        assert err.status_code == 402
        assert err.provider == "firecrawl"

    def test_scrape_failed_error(self) -> None:
        err = FirecrawlScrapeFailedError("https://example.com", "timeout")
        assert err.status_code == 500
        assert "example.com" in err.message
        assert "timeout" in err.message

    def test_scrape_failed_error_no_detail(self) -> None:
        err = FirecrawlScrapeFailedError("https://example.com")
        assert "example.com" in err.message

    def test_crawl_failed_error(self) -> None:
        err = FirecrawlCrawlFailedError("abc-123", "site unreachable")
        assert "abc-123" in err.message
        assert "site unreachable" in err.message

    def test_402_response_raises_credits_error(self, client: FirecrawlClient) -> None:
        resp = _mock_response(402, {"error": "Out of credits"})
        with pytest.raises(FirecrawlCreditsExhaustedError):
            client._check_response(resp)

    def test_401_response_raises_auth_error(self, client: FirecrawlClient) -> None:
        resp = _mock_response(401, {"error": "Unauthorized"})
        with pytest.raises(AuthenticationError):
            client._check_response(resp)

    def test_500_response_raises_provider_unavailable(self, client: FirecrawlClient) -> None:
        resp = _mock_response(500, {"error": "Internal server error"})
        with pytest.raises(ProviderUnavailableError):
            client._check_response(resp)


# ---------------------------------------------------------------------------
# Headers / auth
# ---------------------------------------------------------------------------


class TestHeaders:
    def test_authorization_header(self, client: FirecrawlClient) -> None:
        headers = client._build_headers()
        assert headers["Authorization"] == "Bearer fc-test-key"
        assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

_SEARCH_BODY = {
    "success": True,
    "data": [
        {
            "url": "https://startup.nl",
            "markdown": "# AI Startup\nWe do AI things.",
            "metadata": {"title": "AI Startup NL"},
        },
        {
            "url": "https://company.nl",
            "markdown": "# Company\nSome content.",
            "metadata": {"title": "Company NL"},
        },
    ],
}


class TestSearch:
    @pytest.mark.asyncio
    async def test_returns_parsed_results(self, client: FirecrawlClient) -> None:
        mock_resp = _mock_response(200, _SEARCH_BODY)

        with (
            patch.object(client, "_send", new_callable=AsyncMock, return_value=mock_resp),
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
        ):
            result = await client.search("AI startups in Amsterdam", limit=5)

        assert isinstance(result, SearchResponse)
        assert result.query == "AI startups in Amsterdam"
        assert result.total == 2
        assert len(result.results) == 2
        assert result.results[0].url == "https://startup.nl"
        assert result.results[0].title == "AI Startup NL"
        assert result.results[0].markdown == "# AI Startup\nWe do AI things."

    @pytest.mark.asyncio
    async def test_empty_results(self, client: FirecrawlClient) -> None:
        mock_resp = _mock_response(200, {"success": True, "data": []})

        with (
            patch.object(client, "_send", new_callable=AsyncMock, return_value=mock_resp),
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
        ):
            result = await client.search("nonexistent query")

        assert result.total == 0
        assert result.results == []

    @pytest.mark.asyncio
    async def test_passes_correct_payload(self, client: FirecrawlClient) -> None:
        mock_resp = _mock_response(200, _SEARCH_BODY)

        with (
            patch.object(
                client, "_send", new_callable=AsyncMock, return_value=mock_resp
            ) as mock_send,
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
        ):
            await client.search("test query", limit=3)

        call_kwargs = mock_send.call_args
        json_body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json", {})
        assert json_body["query"] == "test query"
        assert json_body["limit"] == 3
        assert json_body["scrapeOptions"] == {"formats": ["markdown"]}


# ---------------------------------------------------------------------------
# scrape
# ---------------------------------------------------------------------------

_SCRAPE_BODY = {
    "success": True,
    "data": {
        "markdown": "# About Us\nWe are a company.",
        "metadata": {
            "title": "About - Example",
            "statusCode": 200,
        },
    },
}


class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_parsed_result(self, client: FirecrawlClient) -> None:
        mock_resp = _mock_response(200, _SCRAPE_BODY)

        with (
            patch.object(client, "_send", new_callable=AsyncMock, return_value=mock_resp),
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
        ):
            result = await client.scrape("https://example.com/about")

        assert isinstance(result, ScrapeResponse)
        assert result.url == "https://example.com/about"
        assert result.markdown == "# About Us\nWe are a company."
        assert result.title == "About - Example"
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_empty_data_raises_scrape_failed(self, client: FirecrawlClient) -> None:
        mock_resp = _mock_response(200, {"success": True, "data": {}})

        with (
            patch.object(client, "_send", new_callable=AsyncMock, return_value=mock_resp),
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
        ):
            with pytest.raises(FirecrawlScrapeFailedError):
                await client.scrape("https://bad-site.com")

    @pytest.mark.asyncio
    async def test_default_formats_markdown(self, client: FirecrawlClient) -> None:
        mock_resp = _mock_response(200, _SCRAPE_BODY)

        with (
            patch.object(
                client, "_send", new_callable=AsyncMock, return_value=mock_resp
            ) as mock_send,
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
        ):
            await client.scrape("https://example.com")

        json_body = mock_send.call_args.kwargs.get("json") or mock_send.call_args[1].get("json", {})
        assert json_body["formats"] == ["markdown"]

    @pytest.mark.asyncio
    async def test_custom_formats(self, client: FirecrawlClient) -> None:
        mock_resp = _mock_response(200, _SCRAPE_BODY)

        with (
            patch.object(
                client, "_send", new_callable=AsyncMock, return_value=mock_resp
            ) as mock_send,
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
        ):
            await client.scrape("https://example.com", formats=["markdown", "html"])

        json_body = mock_send.call_args.kwargs.get("json") or mock_send.call_args[1].get("json", {})
        assert json_body["formats"] == ["markdown", "html"]


# ---------------------------------------------------------------------------
# crawl
# ---------------------------------------------------------------------------

_CRAWL_START_BODY = {"success": True, "id": "crawl-abc-123"}

_CRAWL_POLLING_BODY = {"status": "scraping", "total": 5, "completed": 2}

_CRAWL_COMPLETED_BODY = {
    "status": "completed",
    "total": 2,
    "data": [
        {
            "markdown": "# Home\nWelcome.",
            "metadata": {
                "title": "Home",
                "sourceURL": "https://example.com/",
                "statusCode": 200,
            },
        },
        {
            "markdown": "# Blog\nLatest posts.",
            "metadata": {
                "title": "Blog",
                "sourceURL": "https://example.com/blog",
                "statusCode": 200,
            },
        },
    ],
}

_CRAWL_FAILED_BODY = {"status": "failed", "error": "Site blocked crawler"}


class TestCrawl:
    @pytest.mark.asyncio
    async def test_start_and_poll_to_completion(self, client: FirecrawlClient) -> None:
        start_resp = _mock_response(200, _CRAWL_START_BODY)
        poll_resp = _mock_response(200, _CRAWL_POLLING_BODY)
        done_resp = _mock_response(200, _CRAWL_COMPLETED_BODY)

        # _send returns: start → poll (scraping) → poll (completed)
        send_mock = AsyncMock(side_effect=[start_resp, poll_resp, done_resp])

        with (
            patch.object(client, "_send", send_mock),
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
            patch("app.services.api.firecrawl.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await client.crawl("https://example.com", max_pages=10)

        assert isinstance(result, CrawlResponse)
        assert result.crawl_id == "crawl-abc-123"
        assert result.status == CrawlStatus.COMPLETED
        assert len(result.pages) == 2
        assert result.pages[0].url == "https://example.com/"
        assert result.pages[0].title == "Home"
        assert result.pages[1].url == "https://example.com/blog"
        assert result.total == 2

    @pytest.mark.asyncio
    async def test_crawl_failed_raises_error(self, client: FirecrawlClient) -> None:
        start_resp = _mock_response(200, _CRAWL_START_BODY)
        failed_resp = _mock_response(200, _CRAWL_FAILED_BODY)

        send_mock = AsyncMock(side_effect=[start_resp, failed_resp])

        with (
            patch.object(client, "_send", send_mock),
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
            patch("app.services.api.firecrawl.asyncio.sleep", new_callable=AsyncMock),
        ):
            with pytest.raises(FirecrawlCrawlFailedError) as exc_info:
                await client.crawl("https://blocked-site.com")

        assert "Site blocked crawler" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_crawl_no_id_raises_error(self, client: FirecrawlClient) -> None:
        start_resp = _mock_response(200, {"success": True})

        with (
            patch.object(client, "_send", new_callable=AsyncMock, return_value=start_resp),
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
        ):
            with pytest.raises(FirecrawlCrawlFailedError):
                await client.crawl("https://example.com")

    @pytest.mark.asyncio
    async def test_crawl_timeout(self, client: FirecrawlClient) -> None:
        client.crawl_max_poll_time = 3.0
        client.crawl_poll_interval = 1.0

        start_resp = _mock_response(200, _CRAWL_START_BODY)
        poll_resp = _mock_response(200, _CRAWL_POLLING_BODY)

        # Always return "scraping" status to trigger timeout
        send_mock = AsyncMock(side_effect=[start_resp, poll_resp, poll_resp, poll_resp, poll_resp])

        # Simulate time progression so the timeout loop exits
        # (asyncio.sleep is mocked, so time.monotonic must advance manually)
        monotonic_values = iter([0.0, 0.0, 1.0, 2.0, 3.0, 4.0])

        with (
            patch.object(client, "_send", send_mock),
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
            patch("app.services.api.firecrawl.asyncio.sleep", new_callable=AsyncMock),
            patch("time.monotonic", side_effect=monotonic_values),
        ):
            with pytest.raises(TimeoutError):
                await client.crawl("https://slow-site.com")

    @pytest.mark.asyncio
    async def test_crawl_passes_include_paths(self, client: FirecrawlClient) -> None:
        start_resp = _mock_response(200, _CRAWL_START_BODY)
        done_resp = _mock_response(200, _CRAWL_COMPLETED_BODY)

        send_mock = AsyncMock(side_effect=[start_resp, done_resp])

        with (
            patch.object(client, "_send", send_mock) as mock_send,
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
            patch("app.services.api.firecrawl.asyncio.sleep", new_callable=AsyncMock),
        ):
            await client.crawl(
                "https://example.com",
                max_pages=5,
                include_paths=["/blog/*", "/about"],
            )

        # Check the start request payload
        first_call = send_mock.call_args_list[0]
        json_body = first_call.kwargs.get("json") or first_call[1].get("json", {})
        assert json_body["includePaths"] == ["/blog/*", "/about"]
        assert json_body["limit"] == 5


# ---------------------------------------------------------------------------
# _parse_crawl_response
# ---------------------------------------------------------------------------


class TestParseCrawlResponse:
    def test_parses_pages(self) -> None:
        result = FirecrawlClient._parse_crawl_response("test-id", _CRAWL_COMPLETED_BODY)
        assert result.crawl_id == "test-id"
        assert result.status == CrawlStatus.COMPLETED
        assert len(result.pages) == 2
        assert result.pages[0].markdown == "# Home\nWelcome."

    def test_empty_data(self) -> None:
        result = FirecrawlClient._parse_crawl_response(
            "test-id", {"status": "completed", "data": []}
        )
        assert result.pages == []
        assert result.total == 0
