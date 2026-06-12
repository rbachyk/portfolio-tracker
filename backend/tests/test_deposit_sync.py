from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Deposit, RawBinanceEvent, SyncState, Withdrawal
from app.ingestion.sync_deposits import sync_deposits, sync_withdrawals

EIGHTEEN_PLACES = Decimal("0.000000000000000001")


class FakeWalletClient:
    def __init__(
        self,
        deposits: list[dict] | None = None,
        withdrawals: list[dict] | None = None,
    ) -> None:
        self.deposits = deposits or []
        self.withdrawals = withdrawals or []
        self.deposit_calls: list[dict] = []
        self.withdrawal_calls: list[dict] = []

    def get_deposit_history(
        self,
        *,
        start_time_ms: int,
        end_time_ms: int | None = None,
        coin: str | None = None,
        offset: int = 0,
        limit: int = 1000,
        **kwargs: object,
    ) -> list[dict]:
        self.deposit_calls.append(
            {"coin": coin, "start_time_ms": start_time_ms, "offset": offset, "limit": limit}
        )
        return self.deposits[offset : offset + limit]

    def get_withdraw_history(
        self,
        *,
        start_time_ms: int,
        end_time_ms: int | None = None,
        coin: str | None = None,
        offset: int = 0,
        limit: int = 1000,
        **kwargs: object,
    ) -> list[dict]:
        self.withdrawal_calls.append(
            {"coin": coin, "start_time_ms": start_time_ms, "offset": offset, "limit": limit}
        )
        return self.withdrawals[offset : offset + limit]


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def deposit_payload() -> dict:
    return {
        "id": "deposit-1",
        "amount": "100.5",
        "coin": "USDT",
        "network": "TRX",
        "status": 1,
        "address": "address",
        "addressTag": "",
        "txId": "deposit-tx",
        "insertTime": 1_700_000_000_000,
        "completeTime": 1_700_000_060_000,
        "transferType": 0,
        "walletType": 0,
    }


def withdrawal_payload() -> dict:
    return {
        "id": "withdrawal-1",
        "amount": "0.25",
        "transactionFee": "0.001",
        "coin": "BNB",
        "network": "BSC",
        "status": 6,
        "address": "address",
        "txId": "withdrawal-tx",
        "applyTime": "2023-11-14 22:13:20",
        "completeTime": "2023-11-14 22:14:20",
        "withdrawOrderId": "order-1",
        "transferType": 0,
        "walletType": 0,
    }


def test_deposit_sync_stores_raw_and_normalized_rows_idempotently() -> None:
    db = make_session()
    client = FakeWalletClient(deposits=[deposit_payload()])

    first_inserted = sync_deposits(db, client, start_time_ms=1_600_000_000_000)
    second_inserted = sync_deposits(db, client, start_time_ms=1_600_000_000_000)

    assert first_inserted == 1
    assert second_inserted == 0
    assert len(db.scalars(select(RawBinanceEvent)).all()) == 1
    deposit = db.scalar(select(Deposit))
    assert deposit is not None
    assert deposit.external_id == "deposit:deposit-1:deposit-tx:1700000000000"
    assert deposit.asset_code == "USDT"
    assert deposit.amount.quantize(EIGHTEEN_PLACES) == Decimal("100.500000000000000000")
    assert deposit.network == "TRX"
    assert deposit.tx_id == "deposit-tx"
    sync_state = db.scalar(select(SyncState).where(SyncState.job_name == "sync_deposits"))
    assert sync_state is not None
    assert sync_state.status == "success"


def test_withdrawal_sync_stores_raw_and_normalized_rows() -> None:
    db = make_session()
    client = FakeWalletClient(withdrawals=[withdrawal_payload()])

    inserted = sync_withdrawals(db, client, start_time_ms=1_600_000_000_000)

    assert inserted == 1
    withdrawal = db.scalar(select(Withdrawal))
    assert withdrawal is not None
    assert withdrawal.external_id == "withdrawal:withdrawal-1:withdrawal-tx:2023-11-14 22:13:20"
    assert withdrawal.asset_code == "BNB"
    assert withdrawal.amount.quantize(EIGHTEEN_PLACES) == Decimal("0.250000000000000000")
    assert withdrawal.transaction_fee.quantize(EIGHTEEN_PLACES) == Decimal(
        "0.001000000000000000"
    )
    assert withdrawal.withdraw_order_id == "order-1"
