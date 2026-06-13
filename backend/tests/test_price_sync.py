from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Asset, Base, PriceSnapshot, Symbol, SyncState
from app.ingestion.sync_prices import sync_exchange_info, sync_prices, sync_prices_for_assets


class FakeBinanceClient:
    def get_exchange_info(self, symbols: set[str] | None = None) -> dict:
        assert symbols == {"BTCUSDT"}
        return {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "isSpotTradingAllowed": True,
                }
            ]
        }

    def get_ticker_prices(self, symbols: set[str]) -> list[dict]:
        assert symbols == {"BTCUSDT"}
        return [{"symbol": "BTCUSDT", "price": "50000.125"}]


class ConfigurableExchangeInfoClient:
    def __init__(self, payloads: dict[str, dict]) -> None:
        self.payloads = payloads
        self.calls: list[set[str] | None] = []

    def get_exchange_info(self, symbols: set[str] | None = None) -> dict:
        self.calls.append(symbols)
        requested_symbols = symbols or set(self.payloads)
        return {
            "symbols": [
                self.payloads[symbol]
                for symbol in sorted(requested_symbols)
                if symbol in self.payloads
            ]
        }


class AllTickerClient:
    def get_ticker_prices(self, symbols: set[str] | None = None) -> list[dict]:
        assert symbols is None
        return [
            {"symbol": "BTCUSDT", "price": "50000"},
            {"symbol": "ADAUSDT", "price": "0.50"},
            {"symbol": "NOTUSDT", "price": "1"},
        ]


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_exchange_info_sync_upserts_configured_symbol_and_assets() -> None:
    db = make_session()
    client = FakeBinanceClient()

    synced = sync_exchange_info(db, client, configured_symbols=["btcusdt"])

    assert synced == 1
    assert db.scalars(select(Asset.code).order_by(Asset.code)).all() == ["BTC", "USDT"]
    symbol = db.scalar(select(Symbol).where(Symbol.symbol == "BTCUSDT"))
    assert symbol is not None
    assert symbol.base_asset_code == "BTC"
    assert symbol.quote_asset_code == "USDT"
    assert symbol.status == "TRADING"
    assert symbol.is_spot_trading_allowed is True
    assert symbol.is_enabled is True


def test_exchange_info_sync_deduplicates_shared_quote_asset_and_repeated_runs() -> None:
    db = make_session()
    db.add(Asset(code="USDT"))
    db.commit()
    usdt_id = db.scalar(select(Asset.id).where(Asset.code == "USDT"))
    client = ConfigurableExchangeInfoClient(
        {
            "BTCUSDT": {
                "symbol": "BTCUSDT",
                "status": "TRADING",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "isSpotTradingAllowed": True,
            },
            "ETHUSDT": {
                "symbol": "ETHUSDT",
                "status": "TRADING",
                "baseAsset": "ETH",
                "quoteAsset": "USDT",
                "isSpotTradingAllowed": True,
            },
        }
    )

    first_synced = sync_exchange_info(
        db,
        client,
        configured_symbols=["BTCUSDT", "ETHUSDT"],
    )
    second_synced = sync_exchange_info(
        db,
        client,
        configured_symbols=["BTCUSDT", "ETHUSDT"],
    )

    assert first_synced == 2
    assert second_synced == 2
    assert db.scalars(select(Asset.code).order_by(Asset.code)).all() == [
        "BTC",
        "ETH",
        "USDT",
    ]
    assert db.scalar(select(Asset.id).where(Asset.code == "USDT")) == usdt_id
    assert db.scalars(select(Symbol.symbol).order_by(Symbol.symbol)).all() == [
        "BTCUSDT",
        "ETHUSDT",
    ]


def test_exchange_info_sync_disables_symbols_removed_from_configuration() -> None:
    db = make_session()
    db.add_all(
        [
            Asset(code="BTC"),
            Asset(code="ETH"),
            Asset(code="USDT"),
            Symbol(
                symbol="BTCUSDT",
                base_asset_code="BTC",
                quote_asset_code="USDT",
                status="TRADING",
                is_spot_trading_allowed=True,
                is_enabled=True,
            ),
            Symbol(
                symbol="ETHUSDT",
                base_asset_code="ETH",
                quote_asset_code="USDT",
                status="TRADING",
                is_spot_trading_allowed=True,
                is_enabled=True,
            ),
        ]
    )
    db.commit()
    client = ConfigurableExchangeInfoClient(
        {
            "BTCUSDT": {
                "symbol": "BTCUSDT",
                "status": "TRADING",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "isSpotTradingAllowed": True,
            }
        }
    )

    synced = sync_exchange_info(db, client, configured_symbols=["BTCUSDT"])

    assert synced == 1
    assert client.calls == [{"BTCUSDT"}]
    btc_symbol = db.scalar(select(Symbol).where(Symbol.symbol == "BTCUSDT"))
    eth_symbol = db.scalar(select(Symbol).where(Symbol.symbol == "ETHUSDT"))
    assert btc_symbol is not None
    assert eth_symbol is not None
    assert btc_symbol.is_enabled is True
    assert eth_symbol.is_enabled is False


def test_exchange_info_sync_with_empty_configuration_disables_all_symbols() -> None:
    db = make_session()
    db.add_all(
        [
            Asset(code="BTC"),
            Asset(code="USDT"),
            Symbol(
                symbol="BTCUSDT",
                base_asset_code="BTC",
                quote_asset_code="USDT",
                status="TRADING",
                is_spot_trading_allowed=True,
                is_enabled=True,
            ),
        ]
    )
    db.commit()
    client = ConfigurableExchangeInfoClient({})

    synced = sync_exchange_info(db, client, configured_symbols=[])

    assert synced == 0
    assert client.calls == []
    symbol = db.scalar(select(Symbol).where(Symbol.symbol == "BTCUSDT"))
    assert symbol is not None
    assert symbol.is_enabled is False


def test_price_sync_creates_snapshot_for_enabled_symbol() -> None:
    db = make_session()
    client = FakeBinanceClient()
    sync_exchange_info(db, client, configured_symbols=["BTCUSDT"])

    inserted = sync_prices(db, client)

    assert inserted == 1
    snapshot = db.scalar(select(PriceSnapshot).where(PriceSnapshot.symbol == "BTCUSDT"))
    assert snapshot is not None
    assert snapshot.price == Decimal("50000.125000000000000000")
    sync_state = db.scalar(select(SyncState).where(SyncState.job_name == "sync_prices"))
    assert sync_state is not None
    assert sync_state.status == "success"


def test_price_sync_noops_without_enabled_symbols() -> None:
    db = make_session()
    client = FakeBinanceClient()

    inserted = sync_prices(db, client)

    assert inserted == 0
    assert db.scalars(select(PriceSnapshot)).all() == []


def test_price_sync_for_assets_creates_symbols_and_prices_for_tracked_assets() -> None:
    db = make_session()
    client = AllTickerClient()

    inserted = sync_prices_for_assets(
        db,
        client,
        asset_codes=["ADA", "USDT"],
        base_asset="USDT",
    )

    assert inserted == 1
    assert db.scalars(select(Asset.code).order_by(Asset.code)).all() == ["ADA", "USDT"]
    symbol = db.scalar(select(Symbol).where(Symbol.symbol == "ADAUSDT"))
    assert symbol is not None
    assert symbol.base_asset_code == "ADA"
    assert symbol.quote_asset_code == "USDT"
    assert symbol.is_enabled is True
    snapshot = db.scalar(select(PriceSnapshot).where(PriceSnapshot.symbol == "ADAUSDT"))
    assert snapshot is not None
    assert snapshot.price == Decimal("0.500000000000000000")
