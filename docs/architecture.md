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

## Planned Later Phases

- Binance read-only API client
- Idempotent ingestion and raw event storage
- Ledger event normalization
- FIFO lot accounting and PnL calculations
- Portfolio snapshots and performance endpoints
- Password-protected React dashboard
- Production deployment documentation
