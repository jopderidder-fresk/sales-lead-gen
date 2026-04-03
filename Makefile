COMPOSE := docker compose -f docker/docker-compose.yml

.PHONY: dev up down build migrate seed logs ps clean test lint

## Development — build, start, migrate, seed, and print status
dev:
	$(COMPOSE) up --build -d
	@echo "Waiting for backend to be ready..."
	@until curl -sf http://localhost:8000/health > /dev/null 2>&1; do sleep 1; done
	$(COMPOSE) exec backend alembic upgrade head
	$(COMPOSE) exec backend python -m app.scripts.seed_demo
	@echo ""
	@echo "Development environment ready!"
	@echo "  Backend:  http://localhost:8000"
	@echo "  Frontend: http://localhost:5173"
	@echo "  Docs:     http://localhost:8000/docs"
	@echo ""
	@echo "  Login via Google SSO"

## Start all services in the background
up:
	$(COMPOSE) up -d

## Rebuild and start all services
build:
	$(COMPOSE) up --build -d

## Stop all services
down:
	$(COMPOSE) down

## Run database migrations
migrate:
	@echo "Waiting for backend to be ready..."
	@until curl -sf http://localhost:8000/health > /dev/null 2>&1; do sleep 1; done
	$(COMPOSE) exec backend alembic upgrade head

## Seed demo companies, contacts, signals, and ICP profile (idempotent)
seed:
	$(COMPOSE) exec backend python -m app.scripts.seed_demo

## Show logs (follow mode)
logs:
	$(COMPOSE) logs -f

## Show container status
ps:
	$(COMPOSE) ps

## Stop and remove containers, volumes, and images
clean:
	$(COMPOSE) down -v --rmi local

## Run backend tests
test:
	cd backend && source .venv/bin/activate && python -m pytest tests/ -q

## Run linters
lint:
	cd backend && source .venv/bin/activate && ruff check app/
	cd frontend && pnpm run lint
