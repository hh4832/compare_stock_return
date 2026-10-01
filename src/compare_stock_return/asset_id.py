"""Explicit market identifiers; the parser never guesses a market."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AssetId:
    asset_id: str
    symbol: str
    market: str
    currency: str
    provider: str


def parse_asset_id(value: str) -> AssetId:
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Z]{2}:[A-Za-z0-9][A-Za-z0-9.\-]*", value
    ):
        raise ValueError("Expected explicit market:ticker identifier")
    market, symbol = value.split(":")
    if market not in {"TW", "US"}:
        raise ValueError(f"Unsupported market: {market}")
    return AssetId(
        value,
        symbol,
        market,
        "TWD" if market == "TW" else "USD",
        "finlab" if market == "TW" else "tiingo",
    )
