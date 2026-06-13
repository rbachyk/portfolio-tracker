# Binance Spot Portfolio Tracker

Production-oriented Binance Spot portfolio tracker with ledger-based accounting, Simple Earn support, PostgreSQL persistence, FastAPI backend, scheduled sync worker, and password-protected React dashboard.

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
- Portfolio snapshots from rebuilt lots and latest prices
- Equity curve and drawdown performance endpoints
- Bcrypt-backed single-user dashboard authentication
- Dashboard APIs for overview, holdings, lots, Earn, deposits, settings, symbols, and sync status
- Spot account balance sync for free/locked Spot quantity
- Manual adjustment ledger events
- Settings, target allocation, user, and Spot balance tables
- Docker Compose frontend and worker services
- React + TypeScript dashboard with login, overview, holdings, lots, Earn, deposits, performance, settings, and sync status pages
- Production Caddy reverse proxy example
- PostgreSQL backup and restore scripts
- Production deployment, security, accounting, Binance API, and dashboard docs

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 22+ for local frontend development
- Docker and Docker Compose

## Local Setup

```bash
cp .env.example .env
make install
make frontend-install
make db-up
make migrate
make dev
```

The backend will run at:

```text
http://localhost:8000
```

Run the dashboard locally in another shell:

```bash
make frontend-dev
```

The Vite dashboard runs at:

```text
http://localhost:5173
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
- `worker` for scheduled sync jobs
- `frontend` on port `3000`

Stop the stack with:

```bash
make docker-down
```

## Production Deployment

Production setup is documented in:

- `docs/deployment.md`
- `docs/security.md`
- `docs/accounting-rules.md`
- `docs/binance-api-map.md`
- `docs/dashboard-spec.md`

The Caddy reverse proxy example is `deploy/Caddyfile.example`.

Create a PostgreSQL backup:

```bash
sh scripts/backup-postgres.sh
```

Restore a backup:

```bash
sh scripts/restore-postgres.sh backups/postgres_YYYYMMDDTHHMMSSZ.sql.gz
```

## Tests

```bash
make test
make lint
make frontend-build
```

The tests cover the application skeleton, auth, Binance request signing/client behavior, price sync logic, trade sync idempotency, wallet history sync, Simple Earn sync, FIFO accounting behavior, portfolio snapshots, and performance endpoints with mocked inputs. They do not call Binance.

## Authentication

The dashboard and portfolio APIs require a bearer token from `/api/auth/login`.
Create a bcrypt password hash and a session secret before running the dashboard:

```bash
uv run --project backend python -c "from app.services.auth_service import hash_password; print(hash_password('replace-this-password'))"
openssl rand -hex 32
```

Put those values in `.env`:

```text
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD_HASH=<bcrypt hash>
SESSION_SECRET=<random hex secret>
```

The first successful login seeds the local `users` table from the configured hash. Password changes after that are stored as bcrypt hashes in PostgreSQL.

## Accounting

The accounting engine currently supports FIFO lot rebuilding only. LIFO, HIFO,
and average cost are reserved for later phases and intentionally rejected if
selected.

Spot buys create acquisition lots. Spot sells consume open lots using FIFO and
record realized PnL on the consumed quantity. Earn rewards create zero-cost lots
and can be reported separately from market price movement. Earn subscriptions
and redemptions are ledger movement events only; they do not create PnL or cost
basis changes.

## Portfolio Snapshots

Create a snapshot after prices are synced and lots have been rebuilt. API calls below require an `Authorization: Bearer <token>` header:

```bash
curl -X POST http://localhost:8000/api/portfolio/snapshots
```

Read stored performance data:

```bash
curl http://localhost:8000/api/portfolio/snapshots/latest
curl http://localhost:8000/api/portfolio/performance/equity-curve
curl http://localhost:8000/api/portfolio/performance/drawdown
```

Snapshot creation requires a current price for every held asset in the configured
portfolio base asset, default `USDT`. If a price is missing, the API returns a
400 response listing the assets that need prices.

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

## History Sync Backfill

Before the first Spot trade sync, set `BINANCE_TRADE_SYNC_START_MS` to a Unix
timestamp in milliseconds earlier than the first trade you want tracked. If that
value is not set, Spot trade sync falls back to `BINANCE_HISTORY_SYNC_START_MS`.
The sync refuses an initial backfill only when both values are missing, so it
cannot silently ingest only Binance's most recent trade page.

Deposit, withdrawal, Simple Earn, P2P order, and Funding transfer history sync
functions require `BINANCE_HISTORY_SYNC_START_MS` for scheduled or API-triggered
backfills. P2P order and Funding transfer history are synced in bounded windows
because Binance limits those APIs to recent history. For older P2P capital that
Binance no longer returns, add a manual adjustment or import it separately.

After the first Simple Earn backfill, subscription, redemption, and reward syncs
resume from the newest stored Earn record with a short overlap instead of
requesting the full history range every run.

If older P2P orders are no longer available from Binance's P2P API, add dated
manual adjustments in the portfolio base asset. Positive base-asset adjustments
increase deposited capital, and negative base-asset adjustments increase
withdrawn capital.

## Sync Worker

The worker container runs these default intervals, all configurable in `.env`:

- prices/exchange info: every 5 minutes
- account/trades/deposits/withdrawals/Earn records: every 30 minutes
- accounting refresh and portfolio snapshot: every 1 hour
- full reconciliation: once per day

The Sync Status dashboard page can trigger grouped jobs:

- `market_sync`
- `records_sync`
- `accounting_refresh`
- `full_reconciliation`

Manual sync triggers return immediately and continue in the backend process. Use
the Sync Status page to follow progress and completion.

## Security Notes

- Do not commit `.env` or any local secret file.
- `.env.example` contains development placeholders only.
- Binance API credentials are read from environment variables only.
- `BINANCE_API_KEY` and `BINANCE_API_SECRET` must stay in `.env` or another git-ignored secret source.
- Use a read-only Binance API key. Do not enable trading permissions for this application.
- Keep `SESSION_SECRET` and `DASHBOARD_PASSWORD_HASH` out of git.
- Restrict the Binance API key to the VPS IP address when available in your Binance account.

## Suggested Commit

```text
add production deployment docs and backup scripts
```
