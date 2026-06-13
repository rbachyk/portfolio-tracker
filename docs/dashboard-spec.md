# Dashboard Spec

## Login

Single-user password login. The frontend receives a bearer token and never sees
Binance credentials.

## Overview

Cards:

- Total equity.
- Deposited capital.
- Unrealized PnL.
- Unrealized PnL percentage.
- Realized PnL.
- Realized PnL percentage.
- 24h change.
- Earn rewards value.
- Asset count.
- Last sync time.

Charts:

- Total equity curve.
- Allocation.
- PnL by symbol.
- Deposits over time.
- Cost basis vs market value.

## Holdings

Shows assets with current positive Spot and/or Earn quantity. Historical lots for
assets no longer held are hidden from Holdings.

## Lots

Shows open lots for current Holdings assets. Closed lots are excluded from the
default dashboard view.

## Earn

Shows current Earn positions, rewards by asset, rewards over time, recent rewards,
subscriptions, and redemptions. Long tables are paginated.

## Deposits

Shows deposits, withdrawals, P2P orders, Funding transfers, and deposits over
time. Funding transfers are displayed for auditability but are not counted as new
capital.

## Performance

Shows equity curve, snapshots, and drawdown from stored portfolio snapshots.

## Settings

Shows runtime settings, target allocations, password change, and manual capital
or asset adjustments.

## Sync Status

Shows job status, progress, start/completion time, and error messages. Manual
sync triggers start background work and return immediately.
