# Security

## Secrets

- Never commit `.env` or backup files.
- Keep `BINANCE_API_KEY`, `BINANCE_API_SECRET`, `SESSION_SECRET`, and
  `DASHBOARD_PASSWORD_HASH` only in the deployment environment.
- Use a unique `POSTGRES_PASSWORD` in production.
- Rotate credentials if they are pasted into logs, tickets, screenshots, or chat.

## Binance API Key

- Use a read-only Binance API key.
- Do not enable trading or withdrawal permissions.
- Restrict the key to the VPS public IP when your Binance account supports it.
- Revoke and recreate the key when moving to a new VPS IP.

## Dashboard Access

- Put the app behind HTTPS.
- Use a long random `SESSION_SECRET`.
- Use a strong dashboard password and store only the bcrypt hash.
- Set `CORS_ALLOWED_ORIGINS` to the production HTTPS origin.
- Do not expose the backend port publicly when Caddy is used; publish the frontend
  on `127.0.0.1:3000` and let Caddy proxy to it.

## Database And Backups

- PostgreSQL data is stored in the Docker volume `postgres_data`.
- Backups may contain balances, transaction history, and API-derived records.
- Keep backups encrypted or stored in a private location.
- Test restores periodically on a non-production machine.

## Operational Notes

- Structured logs must not include API secrets.
- The frontend never receives Binance credentials.
- Manual capital adjustments should include a clear reason for auditability.
