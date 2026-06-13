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

Initial backfills use `BINANCE_TRADE_SYNC_START_MS`, falling back to
`BINANCE_HISTORY_SYNC_START_MS` when the trade-specific value is not set. The
system refuses an initial trade backfill only when both values are missing, so it
does not silently ingest only Binance's most recent trade page. Once a symbol has
synced trades, later runs continue from the highest stored Binance trade id.

Idempotency is enforced with deterministic raw event ids and a unique normalized
trade key on `symbol` plus Binance trade id. Re-running trade sync does not duplicate
existing trades.

## Phase 4

Wallet and Simple Earn ingestion store raw Binance payloads first, then upsert
normalized records for:

- `deposits`
- `withdrawals`
- `p2p_orders`
- `funding_transfers`
- `earn_positions`
- `earn_subscriptions`
- `earn_redemptions`
- `earn_rewards`

Completed P2P buys and sells are treated as external capital flows. Funding to
Spot transfers are stored for audit and dashboard visibility, but are not counted
as new capital because they are internal wallet movement.

Base-asset manual adjustments are included in capital-flow totals, which gives an
audit trail for older P2P capital that Binance no longer exposes through the API.

Simple Earn positions mirror the latest Binance response; positions missing from
the latest response are marked with zero amount so stale Earn holdings are not
shown. Earn history jobs perform a full configured backfill once, then resume from
the newest stored record with a short overlap.

Earn subscriptions and redemptions are stored as movement records, not profit/loss
events. Earn rewards are stored separately with `cost_basis_mode = ZERO`, preserving
the current accounting assumption for Phase 5.

## Phase 5

Accounting now runs from normalized ledger events instead of current balances.
`ledger_events` provides the auditable event stream built from trades, wallet
history, and Simple Earn records. `lots` stores the rebuilt FIFO cost-basis state.

Spot buys create acquisition lots, and spot sells consume the oldest open lots
first while recording realized PnL on the consumed quantity. Earn rewards create
zero-cost acquisition lots so reward quantity and reward value can be reported
separately from market price movement. Earn subscriptions and redemptions remain
movement events only; they do not create or consume lots.

The accounting module exposes lot-level and symbol-level PnL helpers. FIFO is
the only implemented cost-basis method in this phase; LIFO, HIFO, and average
cost are reserved for future work.

## Phase 6

Portfolio snapshots are immutable aggregate records built from the current FIFO
lots and latest available price snapshots in the configured portfolio base asset.
Snapshot creation fails if any held asset is missing a current price, avoiding a
partial or misleading total equity value.

Each snapshot stores total equity, cost basis, base-asset cash flows, realized
PnL, unrealized PnL with and without Earn rewards, Earn reward value, and a JSON
holdings breakdown. Performance endpoints read from stored snapshots to return
equity curve and drawdown data.

Overview cards display gross deposited capital, current unrealized PnL, current
unrealized PnL percentage against open cost basis, all-time realized PnL, and
all-time realized PnL percentage against gross deposited capital.

The snapshot layer assumes `build_ledger`, `rebuild_lots`, and `sync_prices` have
already run. It does not call Binance and does not reconstruct historical prices.

## Phase 7

The application now has a password-protected dashboard and scheduled worker.

Backend additions:

- `users` stores the local dashboard user with a bcrypt password hash.
- `settings` stores dashboard-editable runtime preferences.
- `target_allocations` stores configured target weights by asset.
- `spot_balances` stores the latest free/locked Spot account balance per asset.
- `manual_adjustments` stores auditable manual ledger corrections.
- `sync_account_info` records raw Binance account info and updates Spot balances.
- `sync_service` orchestrates individual sync jobs and grouped runs.
- Manual sync API requests enqueue background work and return immediately; progress
  is read from `sync_state`.
- `worker` runs market sync, records sync, accounting refresh, and full reconciliation on configurable intervals.
- Auth, portfolio, holdings, lots, Earn, deposits, settings, symbols, manual adjustment, and sync status APIs are available under `/api`.

Frontend additions:

- React + TypeScript dashboard served by Vite locally and Nginx in Docker.
- Login page uses `/api/auth/login` and stores only the bearer token in browser storage.
- Overview, Holdings, Lots, Earn, Deposits, Performance, Settings, and Sync Status pages call real backend APIs.
- Dashboard quantities intentionally separate Spot balances, Earn positions, and lot-accounting quantities so Earn auto-subscribe movements are not double counted.

## Planned Later Phases

- Production deployment documentation
