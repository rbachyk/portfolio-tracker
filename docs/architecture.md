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

## Phase 4

Wallet and Simple Earn ingestion store raw Binance payloads first, then upsert
normalized records for:

- `deposits`
- `withdrawals`
- `earn_positions`
- `earn_subscriptions`
- `earn_redemptions`
- `earn_rewards`

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

The snapshot layer assumes `build_ledger`, `rebuild_lots`, and `sync_prices` have
already run. It does not call Binance and does not reconstruct historical prices.

## Planned Later Phases

- Password-protected React dashboard
- Production deployment documentation
