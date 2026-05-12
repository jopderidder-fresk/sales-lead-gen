#!/bin/sh
set -e

log() {
  echo "[start.sh $(date -u '+%Y-%m-%d %H:%M:%S')] $*"
}

presence() {
  if [ -n "$1" ]; then
    printf "set"
  else
    printf "unset"
  fi
}

check_postgres() {
  python - <<'PY'
import asyncio
import os
import sys

import asyncpg


async def check() -> None:
    conn = await asyncio.wait_for(
        asyncpg.connect(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            user=os.environ.get("POSTGRES_USER", "sales"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
            database=os.environ.get("POSTGRES_DB", "sales"),
        ),
        timeout=3,
    )
    await conn.close()


try:
    asyncio.run(check())
except Exception as exc:
    print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
    sys.exit(1)
PY
}

check_redis() {
  python - <<'PY'
import os
import sys

from redis import Redis

try:
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        client = Redis.from_url(
            redis_url,
            socket_connect_timeout=3,
            socket_timeout=3,
            decode_responses=True,
        )
    else:
        client = Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            password=os.environ.get("REDIS_PASSWORD") or None,
            socket_connect_timeout=3,
            socket_timeout=3,
            decode_responses=True,
        )
    client.ping()
except Exception as exc:
    print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
    sys.exit(1)
finally:
    try:
        client.close()
    except Exception:
        pass
PY
}

# Only run migrations for the backend service (uvicorn), not celery workers/beat
if [ "$1" = "uvicorn" ]; then
  log "Backend service detected — running migration check"
  log "Runtime config: APP_ENV=${APP_ENV:-unset} APP_DEBUG=${APP_DEBUG:-unset} POSTGRES_HOST=${POSTGRES_HOST:-localhost} POSTGRES_PORT=${POSTGRES_PORT:-5432} POSTGRES_DB=${POSTGRES_DB:-sales} POSTGRES_USER=${POSTGRES_USER:-sales} REDIS_HOST=${REDIS_HOST:-localhost} REDIS_PORT=${REDIS_PORT:-6379} DATABASE_URL=$(presence "${DATABASE_URL:-}") REDIS_URL=$(presence "${REDIS_URL:-}") FERNET_KEY=$(presence "${FERNET_KEY:-}") JWT_SECRET_KEY=$(presence "${JWT_SECRET_KEY:-}") GOOGLE_CLIENT_ID=$(presence "${GOOGLE_CLIENT_ID:-}") GOOGLE_CLIENT_SECRET=$(presence "${GOOGLE_CLIENT_SECRET:-}")"

  log "Validating application configuration..."
  if ! python - <<'PY'
import sys

try:
    from app.core.config import settings
except Exception as exc:
    print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
    sys.exit(1)

print(
    "[config] "
    f"app_env={settings.app_env} "
    f"app_debug={settings.app_debug} "
    f"postgres_host={settings.postgres_host} "
    f"postgres_db={settings.postgres_db} "
    f"postgres_user={settings.postgres_user} "
    f"redis_host={settings.redis_host} "
    f"llm_provider={settings.llm_provider}"
)
PY
  then
    log "ERROR: Application configuration invalid (see output above)"
    exit 1
  fi

  # Wait for PostgreSQL to be ready
  MAX_RETRIES=30
  RETRY=0
  until OUTPUT="$(check_postgres 2>&1)"; do
    RETRY=$((RETRY + 1))
    if [ "$RETRY" -ge "$MAX_RETRIES" ]; then
      log "ERROR: PostgreSQL not reachable after ${MAX_RETRIES} attempts - aborting. Last error: ${OUTPUT}"
      exit 1
    fi
    log "Waiting for PostgreSQL... (${RETRY}/${MAX_RETRIES}) Last error: ${OUTPUT}"
    sleep 1
  done

  log "PostgreSQL is ready"

  # Wait for Redis to be ready. Compose marks Redis healthy first, but this
  # verifies the exact credentials/URL the backend will use.
  MAX_REDIS_RETRIES=30
  REDIS_RETRY=0
  until OUTPUT="$(check_redis 2>&1)"; do
    REDIS_RETRY=$((REDIS_RETRY + 1))
    if [ "$REDIS_RETRY" -ge "$MAX_REDIS_RETRIES" ]; then
      log "ERROR: Redis not reachable after ${MAX_REDIS_RETRIES} attempts - aborting. Last error: ${OUTPUT}"
      exit 1
    fi
    log "Waiting for Redis... (${REDIS_RETRY}/${MAX_REDIS_RETRIES}) Last error: ${OUTPUT}"
    sleep 1
  done

  log "Redis is ready"

  log "Applying migrations..."
  if ! alembic upgrade head 2>&1; then
    log "ERROR: Alembic migration failed (see output above)"
    exit 1
  fi

  log "Seeding default settings..."
  if ! python -m app.core.seed_defaults 2>&1; then
    log "ERROR: Seed defaults failed (see output above)"
    exit 1
  fi

  log "Startup complete — launching application"
else
  log "Non-backend service detected ($1) — skipping migrations"
fi

exec "$@"
