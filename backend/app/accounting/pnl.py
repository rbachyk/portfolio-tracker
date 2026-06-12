from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.accounting.lots import LotState

ZERO = Decimal("0")


@dataclass(frozen=True)
class LotPnL:
    source_event_id: str
    asset_code: str
    symbol: str | None
    remaining_quantity: Decimal
    unit_cost: Decimal
    current_price: Decimal
    cost_basis: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_pct: Decimal | None
    is_reward: bool


@dataclass(frozen=True)
class SymbolPnL:
    asset_code: str
    quantity: Decimal
    average_buy_price: Decimal | None
    cost_basis: Decimal
    market_value: Decimal
    unrealized_pnl_including_rewards: Decimal
    unrealized_pnl_excluding_rewards: Decimal
    reward_quantity: Decimal
    reward_value: Decimal


def calculate_lot_pnl(lot: LotState, current_price: Decimal) -> LotPnL:
    cost_basis = lot.remaining_cost_basis
    market_value = lot.remaining_quantity * current_price
    unrealized_pnl = market_value - cost_basis
    unrealized_pnl_pct = None if cost_basis == ZERO else unrealized_pnl / cost_basis
    return LotPnL(
        source_event_id=lot.source_event_id,
        asset_code=lot.asset_code,
        symbol=lot.symbol,
        remaining_quantity=lot.remaining_quantity,
        unit_cost=lot.unit_cost,
        current_price=current_price,
        cost_basis=cost_basis,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_pct=unrealized_pnl_pct,
        is_reward=lot.is_reward,
    )


def calculate_symbol_pnl(
    lots: list[LotState],
    *,
    current_prices: dict[str, Decimal],
) -> dict[str, SymbolPnL]:
    results: dict[str, SymbolPnL] = {}
    for asset_code in sorted({lot.asset_code for lot in lots}):
        asset_lots = [
            lot for lot in lots if lot.asset_code == asset_code and lot.remaining_quantity > ZERO
        ]
        if not asset_lots:
            continue

        current_price = current_prices[asset_code]
        quantity = sum((lot.remaining_quantity for lot in asset_lots), ZERO)
        market_value = quantity * current_price
        cost_basis = sum((lot.remaining_cost_basis for lot in asset_lots), ZERO)
        reward_quantity = sum(
            (lot.remaining_quantity for lot in asset_lots if lot.is_reward), ZERO
        )
        reward_value = reward_quantity * current_price

        non_reward_lots = [lot for lot in asset_lots if not lot.is_reward]
        non_reward_cost_basis = sum((lot.remaining_cost_basis for lot in non_reward_lots), ZERO)
        non_reward_quantity = sum((lot.remaining_quantity for lot in non_reward_lots), ZERO)
        non_reward_market_value = (
            non_reward_quantity * current_price
        )
        average_buy_price = (
            None
            if not non_reward_lots or non_reward_quantity == ZERO
            else non_reward_cost_basis / non_reward_quantity
        )

        results[asset_code] = SymbolPnL(
            asset_code=asset_code,
            quantity=quantity,
            average_buy_price=average_buy_price,
            cost_basis=cost_basis,
            market_value=market_value,
            unrealized_pnl_including_rewards=market_value - cost_basis,
            unrealized_pnl_excluding_rewards=non_reward_market_value - non_reward_cost_basis,
            reward_quantity=reward_quantity,
            reward_value=reward_value,
        )

    return results
