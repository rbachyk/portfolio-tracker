from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

ZERO = Decimal("0")


@dataclass(frozen=True)
class AccountingEvent:
    event_type: str
    external_id: str
    source_table: str
    source_id: int
    asset_code: str
    quantity: Decimal
    event_time: datetime
    symbol: str | None = None
    quote_asset_code: str | None = None
    quote_quantity: Decimal = ZERO
    unit_price: Decimal | None = None
    fee_asset_code: str | None = None
    fee_amount: Decimal = ZERO
    metadata: dict = field(default_factory=dict)

    @property
    def is_acquisition(self) -> bool:
        return self.event_type in {"SPOT_BUY", "EARN_REWARD"}

    @property
    def is_disposal(self) -> bool:
        return self.event_type == "SPOT_SELL"

    @property
    def is_reward(self) -> bool:
        return self.event_type == "EARN_REWARD"
