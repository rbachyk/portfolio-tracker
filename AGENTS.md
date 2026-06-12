You are Codex working as a senior full-stack engineer, backend architect, and portfolio accounting specialist.

Your task is to build a production-ready crypto portfolio tracker for Binance Spot that can run on a VPS.

Project name:
binance-spot-portfolio-tracker

Primary goal:
Build a secure, maintainable, version-controlled web application that tracks a Binance Spot portfolio with accurate transaction-level accounting, Binance Simple Earn support, portfolio snapshots, and a password-protected dashboard.

Context:
The user has a long-term crypto portfolio on Binance Spot. Most or all tokens are subscribed to Binance Simple Earn. Earn rewards are deposited daily to Spot and then automatically subscribed again to Earn. The tracker must account for this correctly. The system does not need real-time updates. It should update frequently by scheduled sync jobs.

Core requirements:

1. Connect to Binance using API key and API secret.
2. Use read-only API access only.
3. Never store secrets in git.
4. Run locally in development and on a VPS in production.
5. Use Docker Compose for deployment.
6. Use PostgreSQL as persistent database.
7. Use FastAPI for backend.
8. Use React + TypeScript for frontend dashboard.
9. Use Alembic for database migrations.
10. Use structured logging.
11. Include tests for all accounting logic.
12. Keep the code clean, modular, and suitable for Cursor or VS Code.
13. Keep all files version-controlled with git.
14. Write complete deployment instructions.

Important Binance API constraints:

* Binance Spot trade history endpoint GET /api/v3/myTrades works per symbol.
* The system must therefore discover or configure relevant symbols and sync trades symbol-by-symbol.
* Binance Simple Earn has separate endpoints for flexible/locked positions, subscription records, redemption records, and rewards history.
* Earn subscription and redemption movements are transfers between Spot and Earn, not profit/loss events.
* Earn rewards increase asset quantity and should be tracked separately from buys.

Main product behavior:
The app should show:

1. Total portfolio value.
2. Total deposited capital.
3. Current unrealized profit/loss.
4. Profit/loss by symbol.
5. Average buy price by symbol.
6. Current quantity by symbol.
7. Quantity in Spot.
8. Quantity in Earn.
9. Total quantity including Earn.
10. Market value by symbol.
11. Cost basis by symbol.
12. Earn rewards by symbol.
13. Earn rewards over time.
14. Profit/loss for each individual buy transaction or lot.
15. Equity curve by timeframe.
16. Portfolio allocation by symbol.
17. Deposits over time.
18. Drawdown curve.
19. Target allocation vs actual allocation if targets are configured.
20. Optional toggle to include or exclude Earn rewards in PnL calculations.

Accounting model:
Use a ledger-based architecture.

Create normalized internal events:

* DEPOSIT
* WITHDRAWAL
* SPOT_BUY
* SPOT_SELL
* TRADE_FEE
* EARN_SUBSCRIPTION
* EARN_REDEMPTION
* EARN_REWARD
* PRICE_SNAPSHOT
* PORTFOLIO_SNAPSHOT
* MANUAL_ADJUSTMENT

Cost basis:
Implement lot-based accounting.

Default cost basis method:
FIFO

Also design the system so it can later support:

* LIFO
* HIFO
* AVERAGE

For each buy transaction:

* store symbol
* base asset
* quote asset
* executed quantity
* quote quantity
* fee asset
* fee amount
* executed price
* timestamp
* Binance trade id
* Binance order id
* cost basis
* remaining quantity
* realized PnL if partially or fully sold later
* unrealized PnL based on current price

For Earn rewards:

* store reward asset
* reward amount
* reward timestamp
* product type: flexible or locked
* source endpoint
* cost basis mode:
    * default: reward cost basis = 0
    * allow future setting for tax-specific handling

PnL modes:
Dashboard must support:

1. PnL including Earn rewards.
2. PnL excluding Earn rewards.
3. PnL only from market price movement.
4. Earn rewards value separately.

Important:
Do not treat Earn subscription/redemption as buy/sell.
Do not double-count assets that are in Earn.
Do not double-count daily rewards that are deposited to Spot and then subscribed again.
Do not assume Spot balance alone equals total holdings.
Do not assume average buy price is enough for exact PnL.
Do not build accounting directly from current balances only.

Backend architecture:
Use Python 3.12.

Suggested backend structure:
backend/
app/
main.py
config.py
db/
session.py
models.py
binance/
client.py
signing.py
endpoints.py
rate_limit.py
ingestion/
sync_trades.py
sync_deposits.py
sync_earn.py
sync_prices.py
sync_snapshots.py
accounting/
ledger_builder.py
cost_basis.py
pnl.py
lots.py
rewards.py
api/
routes_auth.py
routes_portfolio.py
routes_symbols.py
routes_lots.py
routes_snapshots.py
routes_settings.py
services/
portfolio_service.py
sync_service.py
settings_service.py
tests/

Database entities:
Design and implement tables for:

* users or local auth config
* settings
* sync_state
* assets
* symbols
* raw_binance_events
* ledger_events
* trades
* deposits
* withdrawals
* earn_positions
* earn_subscriptions
* earn_redemptions
* earn_rewards
* price_snapshots
* portfolio_snapshots
* lots
* target_allocations
* manual_adjustments

Data ingestion:
Implement idempotent sync.
Every Binance object must have a unique external id or deterministic id.
Re-running sync must not duplicate data.
Store raw API payloads for auditability.
Store normalized events for accounting.

Sync jobs:

1. sync_account_info
2. sync_spot_trades
3. sync_deposits
4. sync_withdrawals
5. sync_earn_positions
6. sync_earn_subscriptions
7. sync_earn_redemptions
8. sync_earn_rewards
9. sync_prices
10. build_ledger
11. rebuild_lots
12. create_portfolio_snapshot

Scheduler:
Use a simple scheduler suitable for Docker Compose.
Recommended:

* APScheduler inside backend worker process, or
* separate backend worker container.

Default sync frequency:

* prices: every 5 minutes
* trades/deposits/earn records: every 30 minutes
* portfolio snapshot: every 1 hour
* full reconciliation: once per day

Make these intervals configurable in .env or dashboard settings.

Frontend dashboard:
Use React + TypeScript.

Pages:

1. Login
2. Overview
3. Holdings
4. Lots / Buy Transactions
5. Earn
6. Deposits
7. Performance
8. Settings
9. Sync Status

Overview page:
Show cards:

* Total equity
* Total deposited capital
* Total PnL
* Total PnL %
* 24h change
* Earn rewards total value
* Number of assets
* Last sync time

Charts:

1. Total equity curve
2. Equity curve excluding deposits
3. PnL by symbol
4. Allocation pie or treemap
5. Target vs actual allocation
6. Cost basis vs market value
7. Earn rewards over time
8. Deposits over time
9. Drawdown curve
10. Portfolio vs BTC and ETH benchmark, if feasible

Holdings table:
Columns:

* Asset
* Total quantity
* Spot quantity
* Earn quantity
* Average buy price
* Current price
* Cost basis
* Market value
* Unrealized PnL
* Unrealized PnL %
* Earn rewards quantity
* Earn rewards value
* Allocation %
* Target %
* Difference from target %

Lots table:
Columns:

* Asset
* Buy date
* Quantity bought
* Remaining quantity
* Buy price
* Current price
* Cost basis
* Current value
* Unrealized PnL
* Unrealized PnL %
* Source trade id
* Fee
* Include/exclude reward mode

Earn page:
Show:

* Earn positions
* Earn rewards by asset
* Earn rewards over time
* Subscriptions
* Redemptions
* Auto-subscribe movements
* Toggle: include Earn rewards in PnL

Settings page:
Include:

* Binance API status
* Sync intervals
* Portfolio base currency, default USDT
* Cost basis method, default FIFO
* Include Earn rewards in PnL default true/false
* Target allocations per asset
* Manual asset inclusion/exclusion
* Password change or auth config instructions

Security:

* Dashboard must be password-protected.
* Support single-user local login.
* Hash password with bcrypt or argon2.
* Use secure session/JWT secret from environment.
* Never expose Binance API key/secret to frontend.
* Binance API credentials must be stored only in environment variables or a secure local config ignored by git.
* Document how to create a read-only Binance API key.
* Recommend IP restriction to VPS IP if Binance supports it for the user account.
* Add .env.example, never commit .env.

Deployment:
Create:

* docker-compose.yml with backend, frontend, postgres, worker if needed.
* Dockerfile for backend.
* Dockerfile for frontend.
* production Caddy reverse proxy example.
* .env.example.
* README.md with local setup and production deployment.
* docs/deployment.md with detailed VPS instructions.
* docs/security.md.
* docs/accounting-rules.md.
* docs/binance-api-map.md.
* docs/dashboard-spec.md.

Development workflow:
Use git from the beginning.
Commit after each stable milestone.
Use meaningful commits:

* init project structure
* add database models
* add Binance client
* add trade sync
* add Earn sync
* add accounting engine
* add dashboard overview
* add Docker deployment
* add docs

Quality requirements:

* Write tests for accounting before relying on dashboard numbers.
* Include fixtures for:
    1. one buy, no rewards
    2. multiple buys, average price
    3. buy with fee in base asset
    4. buy with fee in BNB
    5. Earn reward after buy
    6. Earn subscription/redemption without PnL
    7. partial sell
    8. multiple assets
    9. reward included vs excluded PnL
    10. duplicate sync idempotency

Important implementation guidance:
Start with a minimal but correct vertical slice:
Phase 1:

* Project structure
* FastAPI health endpoint
* PostgreSQL connection
* Alembic
* Docker Compose
* settings config
* README

Phase 2:

* Binance signed client
* account info
* exchange info
* symbol configuration
* price sync

Phase 3:

* trade sync for configured symbols
* raw event storage
* normalized trade storage
* idempotency

Phase 4:

* deposits/withdrawals sync
* Simple Earn positions
* Simple Earn rewards
* Simple Earn subscription/redemption records

Phase 5:

* ledger builder
* FIFO lots
* cost basis
* symbol-level PnL
* lot-level PnL
* tests

Phase 6:

* portfolio snapshots
* equity curve
* drawdown
* performance endpoints

Phase 7:

* React dashboard
* auth
* holdings table
* lots table
* earn page
* charts

Phase 8:

* production deployment
* Caddy config
* backup scripts
* final documentation

Do not skip phases.
Do not build UI before accounting tests pass.
Do not fake Binance data in production logic.
For local development, create test fixtures and mock Binance client.

Deliverables:

1. Complete project repository.
2. Working Docker Compose setup.
3. Backend API.
4. Frontend dashboard.
5. PostgreSQL schema and migrations.
6. Binance sync workers.
7. Accounting engine with tests.
8. Password-protected dashboard.
9. VPS deployment instructions.
10. Clear README.
11. Documentation explaining accounting assumptions and limitations.

When making decisions:
Prefer correctness over speed.
Prefer explicit ledger events over hidden calculations.
Prefer auditability over convenience.
Prefer simple architecture over over-engineered microservices.
Prefer readable code over clever code.

Before coding each phase:

1. Briefly summarize what will be implemented.
2. List files to be created or changed.
3. Implement.
4. Run tests or explain how to run them.
5. Update README or docs if needed.
6. Suggest a git commit message.

Begin with Phase 1.