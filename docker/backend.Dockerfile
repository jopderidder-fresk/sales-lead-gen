FROM python:3.12-slim AS base

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies from lockfile (cached layer — only re-runs when lock/pyproject change)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/requirements.txt && \
    uv pip install --system --no-cache -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Copy application source and prompts (found via WORKDIR in sys.path)
COPY --chown=app:app backend/app ./app
COPY --chown=app:app backend/prompts ./prompts

# Development target: hot-reload with uvicorn
FROM base AS dev
RUN uv export --frozen --no-hashes --no-emit-project --extra dev -o /tmp/requirements-dev.txt && \
    uv pip install --system --no-cache -r /tmp/requirements-dev.txt && \
    rm /tmp/requirements-dev.txt
COPY --chown=app:app backend/ .
EXPOSE 8000
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production target
FROM base AS prod
# curl needed for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
# Alembic migrations
COPY --chown=app:app backend/alembic.ini .
COPY --chown=app:app backend/alembic ./alembic
# Startup script (waits for DB, runs migrations for backend only)
COPY docker/start.sh /start.sh
RUN chmod +x /start.sh
USER app
EXPOSE 8000
ENTRYPOINT ["/start.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--forwarded-allow-ips", "*"]
