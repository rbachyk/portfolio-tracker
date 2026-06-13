from __future__ import annotations


def normalize_asset_code(asset_code: object | None) -> str | None:
    if asset_code is None:
        return None
    normalized = str(asset_code).strip().upper()
    return normalized or None


def is_binance_earn_wrapper_asset(asset_code: object | None) -> bool:
    normalized = normalize_asset_code(asset_code)
    return bool(normalized and normalized.startswith("LD") and len(normalized) > 2)
