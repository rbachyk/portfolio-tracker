# Deployment

This deployment runs PostgreSQL, the FastAPI backend, the worker, and the React
frontend with Docker Compose. Caddy terminates HTTPS on the VPS and proxies to
the frontend container.

## VPS Prerequisites

- A Linux VPS with Docker Engine and Docker Compose.
- A DNS A/AAAA record pointing your domain to the VPS.
- A read-only Binance API key. Do not enable trading permissions.
- Optional but recommended: restrict the Binance API key to the VPS public IP.

## Initial Setup

```bash
git clone <repo-url> binance-spot-portfolio-tracker
cd binance-spot-portfolio-tracker
cp .env.example .env
```

Edit `.env` on the VPS. At minimum set:

- `POSTGRES_PASSWORD`
- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`
- `BINANCE_SYMBOLS`
- `BINANCE_HISTORY_SYNC_START_MS`
- `DASHBOARD_PASSWORD_HASH`
- `SESSION_SECRET`
- `CORS_ALLOWED_ORIGINS`

Generate auth secrets:

```bash
uv run --project backend python -c "from app.services.auth_service import hash_password; print(hash_password('replace-this-password'))"
openssl rand -hex 32
```

For production with Caddy on the host, bind the frontend to localhost:

```text
FRONTEND_PORT=127.0.0.1:3000
CORS_ALLOWED_ORIGINS=https://portfolio.example.com
ENVIRONMENT=production
```

## Start The Stack

```bash
docker compose up -d --build
docker compose run --rm backend uv run --no-sync alembic upgrade head
docker compose ps
```

The worker runs scheduled sync jobs. The dashboard can also start sync jobs from
the Sync Status page; manual triggers return immediately and continue in the
backend process.

## Caddy HTTPS Proxy

Install Caddy on the host. Copy `deploy/Caddyfile.example` to your Caddy config
location and replace:

- `portfolio.example.com`
- `admin@example.com`

Then reload Caddy:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## Backups

Create a compressed PostgreSQL dump:

```bash
sh scripts/backup-postgres.sh
```

Backups are written to `backups/`, which is git-ignored. Copy them off the VPS.

Restore into the running PostgreSQL container:

```bash
sh scripts/restore-postgres.sh backups/postgres_YYYYMMDDTHHMMSSZ.sql.gz
```

Restoring writes into the current database. Take a fresh backup before restoring.

## Upgrades

```bash
git pull
docker compose up -d --build
docker compose run --rm backend uv run --no-sync alembic upgrade head
sh scripts/backup-postgres.sh
```

Run a manual `full_reconciliation` from the dashboard after upgrades that affect
sync or accounting behavior.
