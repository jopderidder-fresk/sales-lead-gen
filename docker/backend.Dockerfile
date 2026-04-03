FROM python:3.12-slim AS base

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

# Install dependencies first (cached layer)
COPY backend/pyproject.toml .
RUN mkdir -p app prompts && pip install --no-cache-dir -e .

# Copy application source and prompts
COPY --chown=app:app backend/app ./app
COPY --chown=app:app backend/prompts ./prompts

# Development target: hot-reload with uvicorn
FROM base AS dev
RUN pip install --no-cache-dir -e ".[dev]"
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
