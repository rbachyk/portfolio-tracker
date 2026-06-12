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
            raise BinanceClientError(
                f"Binance API request failed with status {exc.response.status_code}",
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
