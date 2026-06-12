# Binance Spot Portfolio Tracker

Production-oriented Binance Spot portfolio tracker with ledger-based accounting, Simple Earn support, PostgreSQL persistence, FastAPI backend, and a React dashboard planned for later phases.

## Phase 1 Scope

This phase creates the backend foundation only:

- FastAPI application skeleton
- `/health` and `/health/db` endpoints
- PostgreSQL connection helper
- Alembic migration scaffold
- Docker Compose for backend and PostgreSQL
- Local development Makefile
- Basic backend tests

Binance API integration, accounting logic, authentication, and the frontend dashboard are intentionally not implemented yet.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker and Docker Compose

## Local Setup

```bash
cp .env.example .env
make install
make db-up
make migrate
make dev
```

The backend will run at:

```text
http://localhost:8000
```

Health checks:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/db
```

## Docker Compose

```bash
cp .env.example .env
make docker-up
```

This starts:

- `postgres` on port `5432`
- `backend` on port `8000`

Stop the stack with:

```bash
make docker-down
```

## Tests

```bash
make test
```

The Phase 1 tests cover the application skeleton and health endpoint. They do not require a running database.

## Migrations

Apply migrations:

```bash
make migrate
```

Create a migration after adding models:

```bash
make makemigration m="describe change"
```

## Security Notes

- Do not commit `.env` or any local secret file.
- `.env.example` contains development placeholders only.
- Binance API credentials are not part of Phase 1.
- Future Binance API credentials must be read from environment variables or another git-ignored local secret source.

## Suggested Commit

```text
init project structure
```
