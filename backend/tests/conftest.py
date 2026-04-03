"""Shared test fixtures."""

from unittest.mock import patch

import pytest
from slowapi import Limiter


def _noop_check_request_limit(self, request, *args, **kwargs):
    """No-op rate limit check that sets the state attribute slowapi expects."""
    request.state.view_rate_limit = None


@pytest.fixture(autouse=True)
def _disable_rate_limiter():
    """Disable slowapi rate limiting in all tests to avoid Redis dependency."""
    with patch.object(Limiter, "_check_request_limit", _noop_check_request_limit):
        yield
