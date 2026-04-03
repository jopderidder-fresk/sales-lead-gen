# Sales Platform

A full-stack application with a **FastAPI/Python** backend and **Vite/React/TypeScript** frontend.

## Project Structure

```
├── backend/       # FastAPI Python backend
├── frontend/      # Vite + React + TypeScript frontend
├── docker/        # Dockerfiles and compose configs
├── docs/          # Documentation
├── prompts/       # AI prompt templates
└── backlog/       # Product backlog items
```

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

## Development

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

### CI/CD

GitHub Actions runs on every PR:
- **Lint** — ruff (Python), eslint (TypeScript)
- **Type check** — mypy (Python), tsc (TypeScript)
- **Test** — pytest (Python), vitest (TypeScript)
- **Build** — Docker image builds

## Docker (Local Development)

```bash
cp .env.example .env
make dev
```

This starts all services (backend, frontend, postgres, redis, celery worker, celery beat), runs migrations, and seeds demo data.

- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- Login: `admin` / `admin1234`

## Production Deployment (Hetzner + Coolify)

The repo includes a production-ready Docker Compose file for [Coolify](https://coolify.io/).

### Architecture

```
                    ┌─────────┐
                    │ Traefik │  (Coolify-managed, auto SSL)
                    └────┬────┘
                         │
            ┌────────────┼────────────┐
            │ /api, /health           │ /*
            ▼                         ▼
      ┌──────────┐            ┌──────────┐
      │ Backend  │            │ Frontend │
      │ FastAPI  │            │  nginx   │
      │ :8000    │            │  :80     │
      └────┬─────┘            └──────────┘
           │
     ┌─────┴──────┐
     ▼            ▼
┌──────────┐ ┌──────────┐
│ Postgres │ │  Redis   │
│  :5432   │ │  :6379   │
└──────────┘ └────┬─────┘
                  │
          ┌───────┴───────┐
          ▼               ▼
    ┌───────────┐  ┌─────────────┐
    │  Celery   │  │   Celery    │
    │  Worker   │  │    Beat     │
    └───────────┘  └─────────────┘
```

**Services:**

| Service | Purpose |
|---------|---------|
| **backend** | FastAPI API server |
| **frontend** | nginx serving React SPA |
| **postgres** | PostgreSQL 16 database |
| **redis** | Celery broker + cache |
| **celery-worker** | Task worker (6 queues: celery, discovery, enrichment, monitoring, llm, integrations) |
| **celery-beat** | Periodic task scheduler (11 scheduled tasks via RedBeat) |

### Setup in Coolify

1. **Add resource** → Docker Compose → connect this Git repo

2. **Set Docker Compose path** to:
   ```
   docker/docker-compose.coolify.yml
   ```

3. **Add environment variables** (see `docker/.env.coolify.example` for full reference):

   ```bash
   # Required
   APP_ENV=production
   POSTGRES_PASSWORD=<generate: openssl rand -base64 24>
   REDIS_PASSWORD=<generate: openssl rand -base64 24>
   JWT_SECRET_KEY=<generate: openssl rand -hex 32>
   FERNET_KEY=<generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

   # Domain
   FRONTEND_URL=https://your-domain.com

   # First deploy only (remove after)
   SEED_ADMIN=true
   ```

4. **Set domain** in Coolify UI → Deploy

### How It Works

- **Traefik routing**: `/api/*` and `/health` go to the backend (priority 20), everything else to the frontend (priority 10) — single domain, no CORS needed
- **Migrations**: run automatically on every deploy via `docker/entrypoint.sh`
- **Admin seed**: set `SEED_ADMIN=true` for the first deploy, then remove it
- **Resource usage**: ~2.7 GB RAM total (fits Hetzner CX22 or CX32)
- **Data persistence**: named volumes for postgres and redis

### Switching to Coolify-Managed Databases

To use Coolify's managed PostgreSQL/Redis instead of the included containers:

1. Provision databases in Coolify
2. Set `DATABASE_URL` and `REDIS_URL` directly in env vars
3. Scale the `postgres` and `redis` services to 0 in Coolify

## License

MIT
