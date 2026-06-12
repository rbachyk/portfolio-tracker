# Binance Spot Portfolio Tracker

Production-oriented Binance Spot portfolio tracker with ledger-based accounting, Simple Earn support, PostgreSQL persistence, FastAPI backend, and a React dashboard planned for later phases.

## Current Scope

Implemented so far:

- FastAPI application skeleton
- `/health` and `/health/db` endpoints
- PostgreSQL connection helper
- Alembic migration scaffold
- Docker Compose for backend and PostgreSQL
- Local development Makefile
- Basic backend tests
- Binance Spot REST client for read-only account, exchange info, and ticker price calls
- Binance HMAC signing helper
- Symbol configuration tables and price snapshot storage
- Exchange info and price sync functions with mocked tests
- Spot trade sync for configured symbols
- Raw Binance event storage and normalized trade storage with idempotency
- Deposit and withdrawal history sync
- Simple Earn positions, subscriptions, redemptions, and rewards sync
- Ledger event builder for normalized accounting inputs
- FIFO lot accounting with realized/unrealized PnL helpers
- Symbol-level and lot-level PnL calculations

Portfolio snapshots, authentication, and the frontend dashboard are intentionally not implemented yet.

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

The tests cover the application skeleton, Binance request signing/client behavior, price sync logic, trade sync idempotency, wallet history sync, Simple Earn sync, and FIFO accounting behavior with mocked inputs. They do not call Binance.

## Accounting

The accounting engine currently supports FIFO lot rebuilding only. LIFO, HIFO,
and average cost are reserved for later phases and intentionally rejected if
selected.

Spot buys create acquisition lots. Spot sells consume open lots using FIFO and
record realized PnL on the consumed quantity. Earn rewards create zero-cost lots
and can be reported separately from market price movement. Earn subscriptions
and redemptions are ledger movement events only; they do not create PnL or cost
basis changes.

## Migrations

Apply migrations:

```bash
make migrate
```

`make migrate` runs Alembic inside the Docker Compose backend container so it connects
to the `postgres` service directly. To run Alembic from the host instead, use:

```bash
make migrate-local
```

Create a migration after adding models:

```bash
make makemigration m="describe change"
```

## Trade Sync Backfill

Before the first Spot trade sync, set `BINANCE_TRADE_SYNC_START_MS` to a Unix
timestamp in milliseconds earlier than the first trade you want tracked. The sync
refuses an initial backfill without this value so it cannot silently ingest only
Binance's most recent trade page.

Deposit, withdrawal, and Simple Earn history sync functions also require an
explicit `start_time_ms` argument when called so local backfills are intentional.

## Security Notes

- Do not commit `.env` or any local secret file.
- `.env.example` contains development placeholders only.
- Binance API credentials are read from environment variables only.
- `BINANCE_API_KEY` and `BINANCE_API_SECRET` must stay in `.env` or another git-ignored secret source.
- Use a read-only Binance API key. Do not enable trading permissions for this application.

## Suggested Commit

```text
init project structure
```
