# Architecture

This document will evolve as each phase is implemented.

## Phase 1

The initial architecture contains:

- FastAPI backend application
- PostgreSQL connection via SQLAlchemy
- Alembic migration scaffold
- Docker Compose services for backend and PostgreSQL
- Structured JSON logging foundation
- Basic health endpoint and tests

## Phase 2

The backend now has a small Binance Spot market-data ingestion layer:

- `app.binance` contains endpoint constants, HMAC signing, and a synchronous read-only REST client.
- Signed account requests require credentials from environment variables.
- Public exchange info and ticker price endpoints can be used without credentials.
- `assets`, `symbols`, `price_snapshots`, and `sync_state` tables support configured symbol discovery and price snapshots.
- `app.ingestion.sync_prices` upserts exchange metadata for configured symbols and records price snapshots for enabled symbols.

## Phase 3

Spot trade ingestion is symbol-scoped, matching Binance's `GET /api/v3/myTrades`
constraint. The sync reads enabled/configured symbols, fetches trades per symbol,
stores each raw Binance payload in `raw_binance_events`, and stores normalized rows
in `trades`.

Initial backfills require `BINANCE_TRADE_SYNC_START_MS` so the system does not
silently ingest only Binance's most recent trade page. Once a symbol has synced
trades, later runs continue from the highest stored Binance trade id.

Idempotency is enforced with deterministic raw event ids and a unique normalized
trade key on `symbol` plus Binance trade id. Re-running trade sync does not duplicate
existing trades.

## Planned Later Phases

- Ledger event normalization
- FIFO lot accounting and PnL calculations
- Portfolio snapshots and performance endpoints
- Password-protected React dashboard
- Production deployment documentation
