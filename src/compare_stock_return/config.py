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
    benchmark: str = "0050"
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
    non_trading_dates: dict = field(default_factory=dict)
    progress: bool = True

    def validate(self) -> None:
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
