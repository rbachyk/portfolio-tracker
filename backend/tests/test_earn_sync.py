from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    Base,
    EarnPosition,
    EarnRedemption,
    EarnReward,
    EarnSubscription,
    RawBinanceEvent,
    SyncState,
)
from app.ingestion.sync_earn import (
    sync_earn_positions,
    sync_earn_redemptions,
    sync_earn_rewards,
    sync_earn_subscriptions,
)

EIGHTEEN_PLACES = Decimal("0.000000000000000001")


class FakeEarnClient:
    def __init__(self) -> None:
        self.flexible_positions = {
            "rows": [
                {
                    "productId": "USDT001",
                    "asset": "USDT",
                    "totalAmount": "42.5",
                    "autoSubscribe": True,
                }
            ]
        }
        self.locked_positions = {"rows": []}
        self.subscriptions = {
            "rows": [
                {
                    "purchaseId": "purchase-1",
                    "productId": "USDT001",
                    "asset": "USDT",
                    "amount": "10",
                    "time": 1_700_000_000_000,
                }
            ]
        }
        self.redemptions = {
            "rows": [
                {
                    "redeemId": "redeem-1",
                    "productId": "USDT001",
                    "asset": "USDT",
                    "amount": "2",
                    "time": 1_700_000_010_000,
                }
            ]
        }
        self.rewards = {
            "rows": [
                {
                    "productId": "USDT001",
                    "asset": "USDT",
                    "rewards": "0.01",
                    "type": "REALTIME",
                    "time": 1_700_000_020_000,
                }
            ]
        }

    def get_simple_earn_flexible_positions(self, **kwargs: object) -> dict:
        return self.flexible_positions

    def get_simple_earn_locked_positions(self, **kwargs: object) -> dict:
        return self.locked_positions

    def get_simple_earn_subscription_records(self, **kwargs: object) -> dict:
        return self.subscriptions

    def get_simple_earn_redemption_records(self, **kwargs: object) -> dict:
        return self.redemptions

    def get_simple_earn_rewards_history(self, **kwargs: object) -> dict:
        return self.rewards


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_earn_position_sync_upserts_current_positions() -> None:
    db = make_session()
    client = FakeEarnClient()

    first_upserted = sync_earn_positions(db, client)
    second_upserted = sync_earn_positions(db, client)

    assert first_upserted == 1
    assert second_upserted == 0
    position = db.scalar(select(EarnPosition))
    assert position is not None
    assert position.product_type == "flexible"
    assert position.product_id == "USDT001"
    assert position.asset_code == "USDT"
    assert position.amount.quantize(EIGHTEEN_PLACES) == Decimal("42.500000000000000000")
    assert position.auto_subscribe is True
    assert len(db.scalars(select(RawBinanceEvent)).all()) == 1


def test_earn_position_sync_zeroes_positions_missing_from_latest_response() -> None:
    db = make_session()
    client = FakeEarnClient()

    sync_earn_positions(db, client)
    client.flexible_positions = {"rows": []}
    sync_earn_positions(db, client)

    position = db.scalar(select(EarnPosition))
    assert position is not None
    assert position.amount == Decimal("0E-18")


def test_earn_history_sync_stores_subscriptions_redemptions_and_rewards() -> None:
    db = make_session()
    client = FakeEarnClient()

    subscription_count = sync_earn_subscriptions(
        db,
        client,
        start_time_ms=1_600_000_000_000,
        product_types=("flexible",),
    )
    redemption_count = sync_earn_redemptions(
        db,
        client,
        start_time_ms=1_600_000_000_000,
        product_types=("flexible",),
    )
    reward_count = sync_earn_rewards(
        db,
        client,
        start_time_ms=1_600_000_000_000,
        product_types=("flexible",),
    )

    assert subscription_count == 1
    assert redemption_count == 1
    assert reward_count == 1

    subscription = db.scalar(select(EarnSubscription))
    redemption = db.scalar(select(EarnRedemption))
    reward = db.scalar(select(EarnReward))
    assert subscription is not None
    assert redemption is not None
    assert reward is not None
    assert subscription.amount.quantize(EIGHTEEN_PLACES) == Decimal("10.000000000000000000")
    assert redemption.amount.quantize(EIGHTEEN_PLACES) == Decimal("2.000000000000000000")
    assert reward.amount.quantize(EIGHTEEN_PLACES) == Decimal("0.010000000000000000")
    assert reward.cost_basis_mode == "ZERO"
    assert reward.reward_type == "REALTIME"

    sync_state = db.scalar(select(SyncState).where(SyncState.job_name == "sync_earn_rewards"))
    assert sync_state is not None
    assert sync_state.status == "success"


def test_earn_history_sync_is_idempotent() -> None:
    db = make_session()
    client = FakeEarnClient()

    first_count = sync_earn_rewards(
        db,
        client,
        start_time_ms=1_600_000_000_000,
        product_types=("flexible",),
    )
    second_count = sync_earn_rewards(
        db,
        client,
        start_time_ms=1_600_000_000_000,
        product_types=("flexible",),
    )

    assert first_count == 1
    assert second_count == 0
    assert len(db.scalars(select(EarnReward)).all()) == 1
