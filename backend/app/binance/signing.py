from __future__ import annotations

import hmac
from collections.abc import Mapping
from hashlib import sha256
from urllib.parse import urlencode


def normalize_param_value(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def clean_params(params: Mapping[str, object | None]) -> dict[str, str]:
    return {
        key: normalize_param_value(value)
        for key, value in params.items()
        if value is not None
    }


def build_query_string(params: Mapping[str, object | None]) -> str:
    return urlencode(clean_params(params), doseq=True)


def sign_query_string(secret_key: str, query_string: str) -> str:
    return hmac.new(
        secret_key.encode("utf-8"),
        query_string.encode("utf-8"),
        sha256,
    ).hexdigest()


def build_signed_params(
    secret_key: str,
    params: Mapping[str, object | None],
    *,
    timestamp_ms: int,
    recv_window_ms: int,
) -> dict[str, str]:
    signed_params = clean_params(
        {
            **params,
            "recvWindow": recv_window_ms,
            "timestamp": timestamp_ms,
        }
    )
    query_string = build_query_string(signed_params)
    signed_params["signature"] = sign_query_string(secret_key, query_string)
    return signed_params
