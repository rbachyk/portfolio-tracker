from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from typing import Any

import httpx

from app.binance import endpoints
from app.binance.signing import build_signed_params
from app.config import Settings


class BinanceClientError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class BinanceCredentialsError(BinanceClientError):
    pass


class BinanceClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        api_secret: str | None = None,
        recv_window_ms: int = 5000,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        time_ms: Callable[[], int] | None = None,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.recv_window_ms = recv_window_ms
        self.time_ms = time_ms or (lambda: int(time.time() * 1000))
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> BinanceClient:
        return cls(
            base_url=settings.binance_base_url,
            api_key=settings.binance_api_key_value,
            api_secret=settings.binance_api_secret_value,
            recv_window_ms=settings.binance_recv_window_ms,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> BinanceClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_account_info(self, *, omit_zero_balances: bool = True) -> dict[str, Any]:
        return self._get_signed(
            endpoints.ACCOUNT_INFO,
            params={"omitZeroBalances": omit_zero_balances},
        )

    def get_my_trades(
        self,
        *,
        symbol: str,
        order_id: int | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        from_id: int | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        return self._get_signed(
            endpoints.MY_TRADES,
            params={
                "symbol": symbol.strip().upper(),
                "orderId": order_id,
                "startTime": start_time_ms,
                "endTime": end_time_ms,
                "fromId": from_id,
                "limit": limit,
            },
        )

    def get_deposit_history(
        self,
        *,
        coin: str | None = None,
        status: int | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        offset: int = 0,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        return self._get_signed(
            endpoints.DEPOSIT_HISTORY,
            params={
                "coin": coin,
                "status": status,
                "startTime": start_time_ms,
                "endTime": end_time_ms,
                "offset": offset,
                "limit": limit,
            },
        )

    def get_withdraw_history(
        self,
        *,
        coin: str | None = None,
        status: int | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        offset: int = 0,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        return self._get_signed(
            endpoints.WITHDRAW_HISTORY,
            params={
                "coin": coin,
                "status": status,
                "startTime": start_time_ms,
                "endTime": end_time_ms,
                "offset": offset,
                "limit": limit,
            },
        )

    def get_c2c_order_history(
        self,
        *,
        trade_type: str | None = None,
        start_timestamp_ms: int | None = None,
        end_timestamp_ms: int | None = None,
        page: int = 1,
        rows: int = 100,
    ) -> dict[str, Any]:
        return self._get_signed(
            endpoints.C2C_ORDER_HISTORY,
            params={
                "tradeType": trade_type,
                "startTimestamp": start_timestamp_ms,
                "endTimestamp": end_timestamp_ms,
                "page": page,
                "rows": rows,
            },
        )

    def get_universal_transfer_history(
        self,
        *,
        transfer_type: str,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        current: int = 1,
        size: int = 100,
    ) -> dict[str, Any]:
        return self._get_signed(
            endpoints.UNIVERSAL_TRANSFER_HISTORY,
            params={
                "type": transfer_type,
                "startTime": start_time_ms,
                "endTime": end_time_ms,
                "current": current,
                "size": size,
            },
        )

    def get_simple_earn_flexible_positions(
        self,
        *,
        asset: str | None = None,
        current: int = 1,
        size: int = 100,
    ) -> dict[str, Any]:
        return self._get_signed(
            endpoints.EARN_FLEXIBLE_POSITIONS,
            params={"asset": asset, "current": current, "size": size},
        )

    def get_simple_earn_locked_positions(
        self,
        *,
        asset: str | None = None,
        current: int = 1,
        size: int = 100,
    ) -> dict[str, Any]:
        return self._get_signed(
            endpoints.EARN_LOCKED_POSITIONS,
            params={"asset": asset, "current": current, "size": size},
        )

    def get_simple_earn_subscription_records(
        self,
        *,
        product_type: str,
        asset: str | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        current: int = 1,
        size: int = 100,
    ) -> dict[str, Any]:
        endpoint = self._simple_earn_history_endpoint(
            product_type,
            flexible_endpoint=endpoints.EARN_FLEXIBLE_SUBSCRIPTIONS,
            locked_endpoint=endpoints.EARN_LOCKED_SUBSCRIPTIONS,
        )
        return self._get_signed(
            endpoint,
            params={
                "asset": asset,
                "startTime": start_time_ms,
                "endTime": end_time_ms,
                "current": current,
                "size": size,
            },
        )

    def get_simple_earn_redemption_records(
        self,
        *,
        product_type: str,
        asset: str | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        current: int = 1,
        size: int = 100,
    ) -> dict[str, Any]:
        endpoint = self._simple_earn_history_endpoint(
            product_type,
            flexible_endpoint=endpoints.EARN_FLEXIBLE_REDEMPTIONS,
            locked_endpoint=endpoints.EARN_LOCKED_REDEMPTIONS,
        )
        return self._get_signed(
            endpoint,
            params={
                "asset": asset,
                "startTime": start_time_ms,
                "endTime": end_time_ms,
                "current": current,
                "size": size,
            },
        )

    def get_simple_earn_rewards_history(
        self,
        *,
        product_type: str,
        asset: str | None = None,
        reward_type: str | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        current: int = 1,
        size: int = 100,
    ) -> dict[str, Any]:
        normalized_product_type = product_type.strip().lower()
        endpoint = self._simple_earn_history_endpoint(
            product_type,
            flexible_endpoint=endpoints.EARN_FLEXIBLE_REWARDS,
            locked_endpoint=endpoints.EARN_LOCKED_REWARDS,
        )
        params = {
            "asset": asset,
            "startTime": start_time_ms,
            "endTime": end_time_ms,
            "current": current,
            "size": size,
        }
        if normalized_product_type == "flexible":
            params["type"] = reward_type or "ALL"
        elif reward_type is not None:
            params["type"] = reward_type

        return self._get_signed(
            endpoint,
            params=params,
        )

    def get_exchange_info(self, symbols: Sequence[str] | None = None) -> dict[str, Any]:
        return self._get_public(endpoints.EXCHANGE_INFO, params=self._symbol_params(symbols))

    def get_ticker_prices(
        self, symbols: Sequence[str] | None = None
    ) -> dict[str, Any] | list[dict[str, Any]]:
        return self._get_public(endpoints.TICKER_PRICE, params=self._symbol_params(symbols))

    def _get_public(self, path: str, *, params: dict[str, str] | None = None) -> Any:
        return self._request("GET", path, params=params)

    def _get_signed(self, path: str, *, params: dict[str, object | None]) -> Any:
        if not self.api_key or not self.api_secret:
            raise BinanceCredentialsError(
                "Binance API key and secret are required for signed requests"
            )

        signed_params = build_signed_params(
            self.api_secret,
            params,
            timestamp_ms=self.time_ms(),
            recv_window_ms=self.recv_window_ms,
        )
        return self._request(
            "GET",
            path,
            params=signed_params,
            headers={"X-MBX-APIKEY": self.api_key},
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        try:
            response = self._client.request(method, path, params=params, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            response_text = exc.response.text[:500]
            raise BinanceClientError(
                "Binance API request failed with status "
                f"{exc.response.status_code}: {response_text}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise BinanceClientError("Binance API request failed") from exc

        return response.json()

    @staticmethod
    def _symbol_params(symbols: Sequence[str] | None) -> dict[str, str] | None:
        normalized_symbols = [symbol.strip().upper() for symbol in symbols or [] if symbol.strip()]
        if not normalized_symbols:
            return None
        if len(normalized_symbols) == 1:
            return {"symbol": normalized_symbols[0]}
        return {"symbols": json.dumps(normalized_symbols, separators=(",", ":"))}

    @staticmethod
    def _simple_earn_history_endpoint(
        product_type: str,
        *,
        flexible_endpoint: str,
        locked_endpoint: str,
    ) -> str:
        normalized_product_type = product_type.strip().lower()
        if normalized_product_type == "flexible":
            return flexible_endpoint
        if normalized_product_type == "locked":
            return locked_endpoint
        raise ValueError("Simple Earn product_type must be 'flexible' or 'locked'")
