FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv for fast dependency management (only in builder stage)
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /usr/local/bin/uv

# Install dependencies from lockfile (cached layer)
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/requirements.txt && \
    uv pip install --system --no-cache -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Compile bytecode for faster startup
ENV UV_COMPILE_BYTECODE=1

# Copy application source and prompts
COPY --chown=root:root backend/app ./app
COPY --chown=root:root backend/prompts ./prompts

# Development target: hot-reload with uvicorn
FROM builder AS dev
RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --frozen --no-hashes --no-emit-project --extra dev -o /tmp/requirements-dev.txt && \
    uv pip install --system --no-cache -r /tmp/requirements-dev.txt && \
    rm /tmp/requirements-dev.txt
COPY --chown=root:root backend/ .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production target: slim final image without uv or build tools
FROM python:3.12-slim AS prod

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code from builder
COPY --from=builder /app/app ./app
COPY --from=builder /app/prompts ./prompts

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
