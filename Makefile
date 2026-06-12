.PHONY: help install dev test lint format db-up db-down migrate migrate-local makemigration docker-up docker-down

UV := uv
COMPOSE ?= $(shell if docker compose version >/dev/null 2>&1; then printf "docker compose"; else printf "docker-compose"; fi)

help:
	@printf "Available targets:\n"
	@printf "  make install       Install backend dependencies\n"
	@printf "  make dev           Run FastAPI locally with reload\n"
	@printf "  make test          Run backend tests\n"
	@printf "  make lint          Run Ruff checks\n"
	@printf "  make format        Format backend code\n"
	@printf "  make db-up         Start PostgreSQL only\n"
	@printf "  make db-down       Stop PostgreSQL\n"
	@printf "  make migrate       Apply Alembic migrations through Docker Compose\n"
	@printf "  make migrate-local Apply Alembic migrations from the host\n"
	@printf "  make docker-up     Start the full Compose stack\n"
	@printf "  make docker-down   Stop the full Compose stack\n"

install:
	$(UV) sync --project backend --group dev

dev:
	$(UV) run --project backend --group dev uvicorn app.main:app --reload --app-dir backend --host 0.0.0.0 --port 8000

test:
	$(UV) run --project backend --group dev pytest backend/tests

lint:
	$(UV) run --project backend --group dev ruff check backend

format:
	$(UV) run --project backend --group dev ruff format backend

db-up:
	$(COMPOSE) up -d postgres

db-down:
	$(COMPOSE) stop postgres

migrate:
	$(COMPOSE) run --rm --build backend uv run --no-sync alembic upgrade head

migrate-local:
	$(UV) run --project backend alembic -c backend/alembic.ini upgrade head

makemigration:
	$(UV) run --project backend alembic -c backend/alembic.ini revision --autogenerate -m "$(m)"

docker-up:
	$(COMPOSE) up --build

docker-down:
	$(COMPOSE) down
