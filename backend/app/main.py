from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from app.api.v1.auth import limiter
from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import (
    http_exception_handler,
    internal_error_handler,
    validation_error_handler,
)
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from app.core.redis import redis_client
from app.services.api.base_client import drain_background_tasks

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown events."""
    setup_logging()
    logger.info("Starting Sales Platform API", version=settings.app_version)

    # Load DB-persisted settings (usage limits, slack timing, etc.) into the
    # in-memory singleton so this process uses admin-UI values, not just env defaults.
    from app.core.app_settings_store import load_db_settings_into_config
    from app.core.database import async_session_factory

    async with async_session_factory() as session:
        await load_db_settings_into_config(session)

    yield
    logger.info("Shutting down Sales Platform API")
    await drain_background_tasks()
    await engine.dispose()
    await redis_client.aclose()


app = FastAPI(
    title="Sales Platform API",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.app_debug else None,
    redoc_url="/redoc" if settings.app_debug else None,
)

# Rate limiting (SlowAPI)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# Middleware (order matters — outermost first)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
_cors_credentials = "*" not in settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Exception handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, internal_error_handler)

# Routers
app.include_router(v1_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}
