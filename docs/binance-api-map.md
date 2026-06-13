# Binance API Map

All Binance requests are read-only. Signed requests use the configured API key
and secret on the backend only.

| Sync job | Binance endpoint | Purpose |
| --- | --- | --- |
| `sync_exchange_info` | `GET /api/v3/exchangeInfo` | Discover configured Spot symbols and assets. |
| `sync_prices` | `GET /api/v3/ticker/price` | Store latest prices for configured symbols. |
| `sync_tracked_asset_prices` | `GET /api/v3/ticker/price` | Store prices for currently held assets. |
| `sync_account_info` | `GET /api/v3/account` | Update current Spot balances. |
| `sync_spot_trades` | `GET /api/v3/myTrades` | Sync Spot trades per configured symbol. |
| `sync_deposits` | `GET /sapi/v1/capital/deposit/hisrec` | Sync crypto deposit history. |
| `sync_withdrawals` | `GET /sapi/v1/capital/withdraw/history` | Sync crypto withdrawal history. |
| `sync_p2p_orders` | `GET /sapi/v1/c2c/orderMatch/listUserOrderHistory` | Sync recent P2P buy/sell orders. |
| `sync_funding_transfers` | `GET /sapi/v1/asset/transfer` | Sync Funding and Spot wallet transfers. |
| `sync_earn_positions` | Simple Earn position endpoints | Sync current flexible and locked Earn balances. |
| `sync_earn_subscriptions` | Simple Earn subscription history endpoints | Sync Earn subscription movement records. |
| `sync_earn_redemptions` | Simple Earn redemption history endpoints | Sync Earn redemption movement records. |
| `sync_earn_rewards` | Simple Earn reward history endpoints | Sync Earn reward records. |

## Notes

- Spot trades must be queried symbol-by-symbol.
- Earn subscriptions and redemptions are wallet movements, not buys or sells.
- P2P and universal transfer APIs expose recent history only; older capital
  corrections require manual adjustments or a future import workflow.
- Sync jobs are idempotent and use deterministic external IDs where Binance does
  not provide a stable unique identifier.
