import re
import uuid

import structlog
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

# Accept UUIDs or short alphanumeric IDs (max 64 chars)
_REQUEST_ID_RE = re.compile(r"^[a-zA-Z0-9\-]{1,64}$")


class RequestIDMiddleware:
    """Attach a unique request ID to each request for tracing."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        client_id = request.headers.get("X-Request-ID", "")
        request_id = (
            client_id if (client_id and _REQUEST_ID_RE.match(client_id)) else str(uuid.uuid4())
        )

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append("X-Request-ID", request_id)
            await send(message)

        await self.app(scope, receive, send_with_request_id)


class SecurityHeadersMiddleware:
    """Add standard security headers to every response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append("X-Content-Type-Options", "nosniff")
                headers.append("X-Frame-Options", "DENY")
                headers.append("X-XSS-Protection", "1; mode=block")
                headers.append("Referrer-Policy", "strict-origin-when-cross-origin")
                headers.append(
                    "Content-Security-Policy",
                    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data: https:; font-src 'self'; connect-src 'self'; "
                    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
                )
                headers.append("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
                if settings.app_env == "production":
                    headers.append(
                        "Strict-Transport-Security",
                        "max-age=63072000; includeSubDomains; preload",
                    )
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
