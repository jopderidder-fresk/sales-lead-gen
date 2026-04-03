"""Standardized error hierarchy for external API integrations."""


class APIError(Exception):
    """Base exception for all external API errors.

    Attributes:
        provider: Name of the API provider (e.g. "firecrawl", "hunter").
        status_code: HTTP status code returned by the provider, if any.
        message: Human-readable error description.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        status_code: int | None = None,
    ) -> None:
        self.provider = provider
        self.status_code = status_code
        self.message = message
        super().__init__(message)

    def __repr__(self) -> str:
        parts = [f"message={self.message!r}"]
        if self.provider:
            parts.append(f"provider={self.provider!r}")
        if self.status_code is not None:
            parts.append(f"status_code={self.status_code}")
        return f"{type(self).__name__}({', '.join(parts)})"


class RateLimitError(APIError):
    """Raised when the provider returns a 429 or signals rate limiting.

    Attributes:
        retry_after: Seconds to wait before retrying, if provided by the API.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        provider: str = "",
        retry_after: float | None = None,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message, provider=provider, status_code=429)


class AuthenticationError(APIError):
    """Raised when the provider rejects the API key (401/403)."""

    def __init__(
        self,
        message: str = "Authentication failed",
        *,
        provider: str = "",
        status_code: int = 401,
    ) -> None:
        super().__init__(message, provider=provider, status_code=status_code)


class ProviderUnavailableError(APIError):
    """Raised when the provider is down (5xx) or unreachable (network error)."""

    def __init__(
        self,
        message: str = "Provider unavailable",
        *,
        provider: str = "",
        status_code: int | None = None,
    ) -> None:
        super().__init__(message, provider=provider, status_code=status_code)
