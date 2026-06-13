# Accounting Rules

The application uses a ledger-first accounting model. Binance payloads are stored
as raw events, then normalized into domain records and ledger events.

## Event Treatment

- `DEPOSIT`: external asset inflow.
- `WITHDRAWAL`: external asset outflow including withdrawal fee.
- `SPOT_BUY`: acquisition lot for the base asset.
- `SPOT_SELL`: disposal that consumes open lots.
- `TRADE_FEE`: fee movement for auditability.
- `EARN_SUBSCRIPTION`: movement between Spot and Earn, not PnL.
- `EARN_REDEMPTION`: movement between Earn and Spot, not PnL.
- `EARN_REWARD`: zero-cost acquisition lot by default.
- `MANUAL_ADJUSTMENT`: explicit correction or opening balance entry.

## Cost Basis

- FIFO is the implemented cost basis method.
- LIFO, HIFO, and average cost are reserved for future work and are not silently
  substituted.
- Buy fees in the base asset reduce acquired quantity.
- Buy fees in the quote asset increase cost basis.
- Sell fees adjust proceeds or quantity depending on fee asset.

## PnL Definitions

- Unrealized PnL is calculated from open lots and latest prices.
- Realized PnL is recorded when sell events consume lots.
- Earn rewards are separately tracked as reward quantity and reward value.
- Overview unrealized PnL percentage is current unrealized PnL divided by open
  cost basis.
- Overview realized PnL percentage is all-time realized PnL divided by gross
  deposited capital.

## Capital Flows

- Deposited capital is gross deposits plus completed P2P buys plus positive
  base-asset manual capital adjustments.
- Withdrawn capital is withdrawals plus completed P2P sells plus negative
  base-asset manual capital adjustments.
- Funding to Spot transfers are stored for visibility but not counted as new
  capital because they are internal wallet movement.

## Limitations

- Historical P2P records older than Binance API retention must be entered as
  manual capital adjustments or imported in a future import workflow.
- Snapshot totals require current prices for held assets in the configured base
  asset.
