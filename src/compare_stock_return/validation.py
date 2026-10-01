"""Strict missing-data classification; never fill a price."""

import numpy as np
import pandas as pd


class DataQualityError(ValueError):
    """Contains the report that the pipeline exports even on failure."""

    def __init__(self, report: pd.DataFrame):
        self.report = report
        super().__init__("Invalid/missing prices; see data_quality_report.csv")


def validate_assets(
    assets: dict, non_trading_dates: dict | None = None
) -> pd.DataFrame:
    records = []
    bad = False
    for symbol, frame in assets.items():
        if (
            not isinstance(frame.index, pd.DatetimeIndex)
            or frame.index.has_duplicates
            or not frame.index.is_monotonic_increasing
        ):
            raise ValueError(f"{symbol}: index must be sorted unique DatetimeIndex")
        if not {"raw_close", "adjusted_close"} <= set(frame.columns):
            raise ValueError(f"{symbol}: raw_close and adjusted_close required")
        valid = frame[["raw_close", "adjusted_close"]].notna().all(axis=1)
        if valid.sum() < 2:
            raise ValueError(f"{symbol}: fewer than two usable prices")
        start, end = valid[valid].index[[0, -1]]
        window = frame.loc[start:end, ["raw_close", "adjusted_close"]]
        missing = window.isna().any(axis=1)
        explanations = (non_trading_dates or {}).get(symbol, {})
        # Explicit date->reason evidence supplied by the user/provider; omitted from analysis.
        allowed = {
            pd.Timestamp(d): reason
            for d, reason in explanations.items()
            if reason in {"market_suspension", "legitimate_non_trading"}
        }
        unexpected = sum(d not in allowed for d in window.index[missing])
        invalid = (
            ((window <= 0) | (~np.isfinite(window) & window.notna())).any(axis=1).sum()
        )
        bad |= bool(unexpected or invalid)
        records.append(
            dict(
                ticker=symbol,
                first_valid_date=start,
                last_valid_date=end,
                missing_count=int(missing.sum()),
                unexpected_missing_count=unexpected,
                explained_missing_count=int(missing.sum()) - unexpected,
                invalid_price_count=int(invalid),
                missing_dates=";".join(str(d.date()) for d in window.index[missing]),
                policy="explicit non-trading rows excluded; no price/return fill",
            )
        )
    report = pd.DataFrame(records)
    if bad:
        raise DataQualityError(report)
    return report
