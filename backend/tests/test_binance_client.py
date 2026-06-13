from urllib.parse import parse_qs

import httpx
import pytest

from app.binance.client import BinanceClient, BinanceClientError, BinanceCredentialsError
from app.binance.signing import build_query_string, sign_query_string


def test_hmac_signature_matches_binance_example() -> None:
    params = {
        "symbol": "LTCBTC",
        "side": "BUY",
        "type": "LIMIT",
        "timeInForce": "GTC",
        "quantity": "1",
        "price": "0.1",
        "recvWindow": "5000",
        "timestamp": "1499827319559",
    }

    query_string = build_query_string(params)

    assert (
        sign_query_string(
            "NhqPtmdSJYdKjVHjA7PZj4Mge3R5YNiP1e3UZjInClVN65XAbvqqM6A7H5fATj0j",
            query_string,
        )
        == "c8db56825ae71d6d79447849e617115f4a920fa2acdcab2b053c4b2838bd6b71"
    )


def test_signed_account_request_adds_api_key_timestamp_and_signature() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"accountType": "SPOT", "balances": []})

    client = BinanceClient(
        base_url="https://api.binance.test",
        api_key="api-key",
        api_secret="secret",
        recv_window_ms=5000,
        transport=httpx.MockTransport(handler),
        time_ms=lambda: 1_499_827_319_559,
    )

    response = client.get_account_info()

    assert response["accountType"] == "SPOT"
    assert captured_request is not None
    assert captured_request.url.path == "/api/v3/account"
    assert captured_request.headers["X-MBX-APIKEY"] == "api-key"

    query = parse_qs(captured_request.url.query.decode("utf-8"))
    assert query["omitZeroBalances"] == ["true"]
    assert query["recvWindow"] == ["5000"]
    assert query["timestamp"] == ["1499827319559"]
    assert "signature" in query


def test_signed_request_requires_credentials() -> None:
    client = BinanceClient(base_url="https://api.binance.test")

    with pytest.raises(BinanceCredentialsError):
        client.get_account_info()


def test_error_message_includes_binance_response_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": -1128, "msg": "Time range too large"})

    client = BinanceClient(
        base_url="https://api.binance.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(BinanceClientError, match="Time range too large"):
        client.get_exchange_info(["BTCUSDT"])


def test_exchange_info_uses_symbols_parameter_for_multiple_symbols() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"symbols": []})

    client = BinanceClient(
        base_url="https://api.binance.test",
        transport=httpx.MockTransport(handler),
    )

    client.get_exchange_info(["btcusdt", "ETHUSDT"])

    assert captured_request is not None
    query = parse_qs(captured_request.url.query.decode("utf-8"))
    assert query["symbols"] == ['["BTCUSDT","ETHUSDT"]']


def test_get_my_trades_is_symbol_scoped_and_signed() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json=[])

    client = BinanceClient(
        base_url="https://api.binance.test",
        api_key="api-key",
        api_secret="secret",
        recv_window_ms=5000,
        transport=httpx.MockTransport(handler),
        time_ms=lambda: 1_499_827_319_559,
    )

    response = client.get_my_trades(symbol="btcusdt", from_id=42, limit=1000)

    assert response == []
    assert captured_request is not None
    assert captured_request.url.path == "/api/v3/myTrades"
    assert captured_request.headers["X-MBX-APIKEY"] == "api-key"

    query = parse_qs(captured_request.url.query.decode("utf-8"))
    assert query["symbol"] == ["BTCUSDT"]
    assert query["fromId"] == ["42"]
    assert query["limit"] == ["1000"]
    assert query["recvWindow"] == ["5000"]
    assert query["timestamp"] == ["1499827319559"]
    assert "signature" in query


def test_deposit_history_request_is_signed() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json=[])

    client = BinanceClient(
        base_url="https://api.binance.test",
        api_key="api-key",
        api_secret="secret",
        transport=httpx.MockTransport(handler),
        time_ms=lambda: 1_499_827_319_559,
    )

    client.get_deposit_history(coin="USDT", start_time_ms=1, end_time_ms=2, offset=0, limit=1000)

    assert captured_request is not None
    assert captured_request.url.path == "/sapi/v1/capital/deposit/hisrec"
    query = parse_qs(captured_request.url.query.decode("utf-8"))
    assert query["coin"] == ["USDT"]
    assert query["startTime"] == ["1"]
    assert query["endTime"] == ["2"]
    assert "signature" in query


def test_c2c_order_history_request_is_signed() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"data": []})

    client = BinanceClient(
        base_url="https://api.binance.test",
        api_key="api-key",
        api_secret="secret",
        transport=httpx.MockTransport(handler),
        time_ms=lambda: 1_499_827_319_559,
    )

    client.get_c2c_order_history(
        trade_type="BUY",
        start_timestamp_ms=1,
        end_timestamp_ms=2,
        page=3,
        rows=100,
    )

    assert captured_request is not None
    assert captured_request.url.path == "/sapi/v1/c2c/orderMatch/listUserOrderHistory"
    query = parse_qs(captured_request.url.query.decode("utf-8"))
    assert query["tradeType"] == ["BUY"]
    assert query["startTimestamp"] == ["1"]
    assert query["endTimestamp"] == ["2"]
    assert query["page"] == ["3"]
    assert query["rows"] == ["100"]
    assert "signature" in query


def test_universal_transfer_history_request_is_signed() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"rows": []})

    client = BinanceClient(
        base_url="https://api.binance.test",
        api_key="api-key",
        api_secret="secret",
        transport=httpx.MockTransport(handler),
        time_ms=lambda: 1_499_827_319_559,
    )

    client.get_universal_transfer_history(
        transfer_type="FUNDING_MAIN",
        start_time_ms=1,
        end_time_ms=2,
        current=4,
        size=100,
    )

    assert captured_request is not None
    assert captured_request.url.path == "/sapi/v1/asset/transfer"
    query = parse_qs(captured_request.url.query.decode("utf-8"))
    assert query["type"] == ["FUNDING_MAIN"]
    assert query["startTime"] == ["1"]
    assert query["endTime"] == ["2"]
    assert query["current"] == ["4"]
    assert query["size"] == ["100"]
    assert "signature" in query


def test_simple_earn_history_uses_product_type_endpoint() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"rows": []})

    client = BinanceClient(
        base_url="https://api.binance.test",
        api_key="api-key",
        api_secret="secret",
        transport=httpx.MockTransport(handler),
        time_ms=lambda: 1_499_827_319_559,
    )

    client.get_simple_earn_rewards_history(
        product_type="locked",
        asset="BNB",
        start_time_ms=1,
        current=2,
        size=50,
    )

    assert captured_request is not None
    assert captured_request.url.path == "/sapi/v1/simple-earn/locked/history/rewardsRecord"
    query = parse_qs(captured_request.url.query.decode("utf-8"))
    assert query["asset"] == ["BNB"]
    assert query["startTime"] == ["1"]
    assert query["current"] == ["2"]
    assert query["size"] == ["50"]
    assert "type" not in query
    assert "signature" in query


def test_flexible_earn_rewards_history_sends_default_reward_type() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"rows": []})

    client = BinanceClient(
        base_url="https://api.binance.test",
        api_key="api-key",
        api_secret="secret",
        transport=httpx.MockTransport(handler),
        time_ms=lambda: 1_499_827_319_559,
    )

    client.get_simple_earn_rewards_history(
        product_type="flexible",
        start_time_ms=1,
        end_time_ms=2,
    )

    assert captured_request is not None
    assert captured_request.url.path == "/sapi/v1/simple-earn/flexible/history/rewardsRecord"
    query = parse_qs(captured_request.url.query.decode("utf-8"))
    assert query["type"] == ["ALL"]
    assert query["startTime"] == ["1"]
    assert query["endTime"] == ["2"]
    assert "signature" in query
