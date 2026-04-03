#!/bin/sh
set -e

log() {
  echo "[start.sh $(date -u '+%Y-%m-%d %H:%M:%S')] $*"
}

# Only run migrations for the backend service (uvicorn), not celery workers/beat
if [ "$1" = "uvicorn" ]; then
  log "Backend service detected — running migration check"

  # Wait for PostgreSQL to be ready
  MAX_RETRIES=30
  RETRY=0
  until python -c "
import asyncio, asyncpg, os
async def check():
    await asyncio.wait_for(asyncpg.connect(
        host=os.environ.get('POSTGRES_HOST', 'localhost'),
        port=int(os.environ.get('POSTGRES_PORT', '5432')),
        user=os.environ.get('POSTGRES_USER', 'sales'),
        password=os.environ.get('POSTGRES_PASSWORD', ''),
        database=os.environ.get('POSTGRES_DB', 'sales'),
    ), timeout=3)
asyncio.run(check())
" 2>/dev/null; do
    RETRY=$((RETRY + 1))
    if [ "$RETRY" -ge "$MAX_RETRIES" ]; then
      log "ERROR: PostgreSQL not reachable after ${MAX_RETRIES} attempts — aborting"
      exit 1
    fi
    log "Waiting for PostgreSQL... (${RETRY}/${MAX_RETRIES})"
    sleep 1
  done

  log "PostgreSQL is ready"

  log "Applying migrations..."
  alembic upgrade head

  log "Seeding default settings..."
  python -m app.core.seed_defaults

  log "Startup complete — launching application"
else
  log "Non-backend service detected ($1) — skipping migrations"
fi

exec "$@"
