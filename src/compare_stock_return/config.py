"""Centralized configuration, with no credentials in configuration files."""

from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd
import yaml

DRIVE_OUTPUT_ROOT = "/content/drive/MyDrive/00Quant_Research/compare_stock_return"
TRADING_DAYS = 252


@dataclass
class Config:
    symbols: list[str] = field(default_factory=lambda: ["0050", "009816"])
    assets: list[str] | None = None
    benchmark: str = "TW:0050"
    fx_mode: str = "none"
    portfolios: dict = field(default_factory=dict)
    date_mode: str = "intersection"
    custom_start_date: str | None = None
    custom_end_date: str | None = None
    strict: bool = False
    return_type: str = "total_return"
    risk_free_rate: float = 0.0
    drive_output_root: str = DRIVE_OUTPUT_ROOT
    use_cache: bool = True
    refresh_cache: bool = False
    cache_max_age_hours: float = 24.0
    display_symbols: list[str] | None = None
    fees: dict = field(default_factory=dict)
    custom_assets: dict = field(default_factory=dict)
    holdings_files: dict = field(default_factory=dict)
    non_trading_dates: dict = field(
        default_factory=lambda: {
            "TW:0050": {
                d: "market_suspension"
                for d in [
                    "2025-06-11",
                    "2025-06-12",
                    "2025-06-13",
                    "2025-06-16",
                    "2025-06-17",
                ]
            }
        }
    )
    progress: bool = True

    def validate(self) -> None:
        from .asset_id import parse_asset_id

        if self.fx_mode != "none":
            raise NotImplementedError(
                "FX_MODE must be none; FX conversion is not implemented"
            )
        # Explicit legacy layer only: symbols are Taiwan identifiers. Preserve old fixture/custom keys.
        if self.assets is not None:
            for asset in self.assets:
                parse_asset_id(asset)
            self.symbols = list(self.assets)
            parse_asset_id(self.benchmark)
        elif self.symbols == ["0050", "009816"] and self.benchmark == "TW:0050":
            self.assets = ["TW:0050", "TW:009816"]
            self.symbols = list(self.assets)
        from .model_portfolio import validate_weights

        for weights in self.portfolios.values():
            validate_weights(weights, self.symbols)
        if not self.symbols or any(
            not isinstance(s, str) or not s.strip() for s in self.symbols
        ):
            raise ValueError(
                "symbols must contain nonempty strings (keep leading zeroes)"
            )
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("Duplicate ticker")
        if self.benchmark not in self.symbols:
            raise ValueError("benchmark must exist in symbols")
        if self.date_mode not in {"intersection", "full_history", "custom"}:
            raise ValueError("Invalid date_mode")
        if self.return_type not in {"total_return", "price_return"}:
            raise ValueError("Invalid return_type")
        if self.display_symbols is not None and not set(self.display_symbols) <= set(
            self.symbols
        ):
            raise ValueError("display_symbols must be a subset of symbols")
        if self.risk_free_rate <= -1 or self.cache_max_age_hours <= 0:
            raise ValueError("Invalid rate/cache age")
        for fee in self.fees.values():
            rate = fee.get("annual_expense_ratio")
            if rate is not None and not 0 <= rate < 1:
                raise ValueError("Expense ratios must be decimal fractions in [0,1)")
        if self.date_mode == "custom":
            if not self.custom_start_date or not self.custom_end_date:
                raise ValueError("custom requires both dates")
            if pd.Timestamp(self.custom_start_date) >= pd.Timestamp(
                self.custom_end_date
            ):
                raise ValueError("custom start must precede end")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        with Path(path).open() as f:
            config = cls(**yaml.safe_load(f))
        config.validate()
        return config
