from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, FundingTransfer, P2POrder, RawBinanceEvent, SyncState
from app.ingestion.sync_funding import sync_funding_transfers, sync_p2p_orders

EIGHT_PLACES = Decimal("0.00000001")


class FakeFundingClient:
    def __init__(self) -> None:
        self.p2p_calls: list[dict[str, object]] = []
        self.transfer_calls: list[dict[str, object]] = []

    def get_c2c_order_history(self, **kwargs: object) -> dict:
        self.p2p_calls.append(kwargs)
        if kwargs["trade_type"] == "BUY":
            return {
                "data": [
                    {
                        "orderNumber": "p2p-buy-1",
                        "tradeType": "BUY",
                        "asset": "USDT",
                        "fiat": "EUR",
                        "amount": "100",
                        "totalPrice": "100",
                        "unitPrice": "1",
                        "commission": "0",
                        "orderStatus": "COMPLETED",
                        "payMethodName": "BANK",
                        "createTime": 1_700_000_000_000,
                    }
                ]
            }
        return {
            "data": [
                {
                    "orderNumber": "p2p-sell-1",
                    "tradeType": "SELL",
                    "asset": "USDT",
                    "fiat": "EUR",
                    "amount": "20",
                    "totalPrice": "20",
                    "unitPrice": "1",
                    "commission": "0.1",
                    "orderStatus": "COMPLETED",
                    "payMethodName": "BANK",
                    "createTime": 1_700_000_100_000,
                }
            ]
        }

    def get_universal_transfer_history(self, **kwargs: object) -> dict:
        self.transfer_calls.append(kwargs)
        return {
            "rows": [
                {
                    "asset": "USDT",
                    "amount": "100",
                    "type": kwargs["transfer_type"],
                    "status": "CONFIRMED",
                    "tranId": 123,
                    "timestamp": 1_700_000_200_000,
                }
            ]
        }


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_p2p_sync_stores_buy_and_sell_orders_idempotently() -> None:
    db = make_session()
    client = FakeFundingClient()

    first_count = sync_p2p_orders(db, client, start_time_ms=1, end_time_ms=2)
    second_count = sync_p2p_orders(db, client, start_time_ms=1, end_time_ms=2)

    assert first_count == 2
    assert second_count == 0
    orders = db.scalars(select(P2POrder).order_by(P2POrder.trade_type)).all()
    assert len(orders) == 2
    assert orders[0].trade_type == "BUY"
    assert orders[0].amount == Decimal("100.000000000000000000")
    assert orders[1].trade_type == "SELL"
    assert orders[1].commission.quantize(EIGHT_PLACES) == Decimal("0.10000000")
    assert len(db.scalars(select(RawBinanceEvent)).all()) == 2
    state = db.scalar(select(SyncState).where(SyncState.job_name == "sync_p2p_orders"))
    assert state is not None
    assert state.status == "success"


def test_funding_transfer_sync_stores_funding_spot_movements_idempotently() -> None:
    db = make_session()
    client = FakeFundingClient()

    first_count = sync_funding_transfers(db, client, start_time_ms=1, end_time_ms=2)
    second_count = sync_funding_transfers(db, client, start_time_ms=1, end_time_ms=2)

    assert first_count == 2
    assert second_count == 0
    transfers = db.scalars(select(FundingTransfer).order_by(FundingTransfer.transfer_type)).all()
    assert len(transfers) == 2
    assert {transfer.transfer_type for transfer in transfers} == {"FUNDING_MAIN", "MAIN_FUNDING"}
    assert all(transfer.status == "CONFIRMED" for transfer in transfers)
