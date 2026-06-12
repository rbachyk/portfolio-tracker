from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.accounting.cost_basis import CostBasisMethod, ensure_supported_method
from app.accounting.events import AccountingEvent

ZERO = Decimal("0")


@dataclass
class LotState:
    source_event_id: str
    asset_code: str
    opened_at: datetime
    original_quantity: Decimal
    remaining_quantity: Decimal
    total_cost_basis: Decimal
    source_type: str
    symbol: str | None = None
    realized_pnl: Decimal = ZERO
    is_reward: bool = False

    @property
    def unit_cost(self) -> Decimal:
        if self.original_quantity == ZERO:
            return ZERO
        return self.total_cost_basis / self.original_quantity

    @property
    def remaining_cost_basis(self) -> Decimal:
        return self.remaining_quantity * self.unit_cost


@dataclass(frozen=True)
class LotDisposition:
    source_event_id: str
    sell_event_id: str
    asset_code: str
    quantity: Decimal
    proceeds: Decimal
    cost_basis: Decimal
    realized_pnl: Decimal


@dataclass
class LotRebuildResult:
    lots: list[LotState] = field(default_factory=list)
    dispositions: list[LotDisposition] = field(default_factory=list)

    @property
    def realized_pnl(self) -> Decimal:
        return sum((disposition.realized_pnl for disposition in self.dispositions), ZERO)


def rebuild_lots_from_events(
    events: list[AccountingEvent],
    *,
    method: CostBasisMethod = CostBasisMethod.FIFO,
) -> LotRebuildResult:
    ensure_supported_method(method)
    result = LotRebuildResult()
    open_lots_by_asset: dict[str, list[LotState]] = {}

    for event in sorted(events, key=lambda item: (item.event_time, item.external_id)):
        if event.is_acquisition:
            lot = _lot_from_event(event)
            result.lots.append(lot)
            open_lots_by_asset.setdefault(lot.asset_code, []).append(lot)
            continue

        if event.is_disposal:
            result.dispositions.extend(
                _apply_fifo_sale(open_lots_by_asset.get(event.asset_code, []), event)
            )

    return result


def _lot_from_event(event: AccountingEvent) -> LotState:
    if event.quantity <= ZERO:
        raise ValueError(f"Acquisition event {event.external_id} must have positive quantity")

    return LotState(
        source_event_id=event.external_id,
        asset_code=event.asset_code,
        symbol=event.symbol,
        opened_at=event.event_time,
        original_quantity=event.quantity,
        remaining_quantity=event.quantity,
        total_cost_basis=event.quote_quantity,
        source_type=event.event_type,
        is_reward=event.is_reward,
    )


def _apply_fifo_sale(
    open_lots: list[LotState],
    sell_event: AccountingEvent,
) -> list[LotDisposition]:
    quantity_to_sell = abs(sell_event.quantity)
    if quantity_to_sell <= ZERO:
        return []

    sale_proceeds = sell_event.quote_quantity
    dispositions: list[LotDisposition] = []

    for lot in open_lots:
        if quantity_to_sell == ZERO:
            break
        if lot.remaining_quantity == ZERO:
            continue

        quantity = min(lot.remaining_quantity, quantity_to_sell)
        proceeds = sale_proceeds * (quantity / abs(sell_event.quantity))
        cost_basis = quantity * lot.unit_cost
        realized_pnl = proceeds - cost_basis

        lot.remaining_quantity -= quantity
        lot.realized_pnl += realized_pnl
        quantity_to_sell -= quantity

        dispositions.append(
            LotDisposition(
                source_event_id=lot.source_event_id,
                sell_event_id=sell_event.external_id,
                asset_code=sell_event.asset_code,
                quantity=quantity,
                proceeds=proceeds,
                cost_basis=cost_basis,
                realized_pnl=realized_pnl,
            )
        )

    if quantity_to_sell > ZERO:
        raise ValueError(
            f"Cannot sell {abs(sell_event.quantity)} {sell_event.asset_code}; "
            f"missing {quantity_to_sell} in FIFO lots"
        )

    return dispositions
