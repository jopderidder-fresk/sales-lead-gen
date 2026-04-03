"""Tests for the API error hierarchy."""

from app.services.api.errors import (
    APIError,
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
)


class TestErrorHierarchy:
    def test_all_errors_inherit_from_api_error(self) -> None:
        assert issubclass(RateLimitError, APIError)
        assert issubclass(AuthenticationError, APIError)
        assert issubclass(ProviderUnavailableError, APIError)

    def test_api_error_attributes(self) -> None:
        err = APIError("something broke", provider="hunter", status_code=400)
        assert err.provider == "hunter"
        assert err.status_code == 400
        assert err.message == "something broke"
        assert str(err) == "something broke"

    def test_rate_limit_error_defaults(self) -> None:
        err = RateLimitError(provider="apollo", retry_after=30.0)
        assert err.status_code == 429
        assert err.retry_after == 30.0

    def test_auth_error_defaults(self) -> None:
        err = AuthenticationError(provider="firecrawl")
        assert err.status_code == 401

    def test_provider_unavailable_defaults(self) -> None:
        err = ProviderUnavailableError(provider="snov")
        assert err.status_code is None
        assert err.provider == "snov"

    def test_api_error_repr(self) -> None:
        err = APIError("fail", provider="x", status_code=500)
        r = repr(err)
        assert "APIError" in r
        assert "provider='x'" in r
        assert "status_code=500" in r
