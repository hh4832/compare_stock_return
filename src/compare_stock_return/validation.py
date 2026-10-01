"""Auditable missing-data policy. Never repair or fill source prices."""

import logging

import numpy as np
import pandas as pd

DETAIL_COLUMNS = [
    "asset_id",
    "date",
    "raw_missing",
    "adjusted_missing",
    "reason",
    "status",
]
DAILY_WARNING = "DAILY_METRICS_HAVE_MISSING_SESSION_WARNING"


class DataQualityError(ValueError):
    """Carries both reports so failed runs retain the same audit evidence."""

    def __init__(self, report: pd.DataFrame, details: pd.DataFrame | None = None):
        self.report = report
        self.details = (
            details if details is not None else pd.DataFrame(columns=DETAIL_COLUMNS)
        )
        super().__init__(
            "Invalid/missing prices; see data_quality_report.csv and missing_data_details.csv"
        )


def validate_assets(
    assets: dict,
    non_trading_dates: dict | None = None,
    policy: str = "warn",
    logger=None,
) -> pd.DataFrame:
    if policy not in {"error", "warn", "ignore"}:
        raise ValueError("missing_data_policy must be error, warn or ignore")
    records, details, bad = [], [], False
    for symbol, frame in assets.items():
        if (
            not isinstance(frame.index, pd.DatetimeIndex)
            or frame.index.hasnans
            or frame.index.has_duplicates
            or not frame.index.is_monotonic_increasing
        ):
            raise ValueError(
                f"{symbol}: index must be sorted unique DatetimeIndex without NaT"
            )
        if not {"raw_close", "adjusted_close"} <= set(frame.columns):
            raise ValueError(f"{symbol}: raw_close and adjusted_close required")
        prices = frame[["raw_close", "adjusted_close"]]
        # Validate ALL source values, even a non-missing invalid value opposite a missing value.
        invalid = int(
            ((prices <= 0) | (~np.isfinite(prices) & prices.notna())).any(axis=1).sum()
        )
        valid = prices.notna().all(axis=1)
        usable_count = int(valid.sum())
        start, end = valid[valid].index[[0, -1]] if usable_count else (pd.NaT, pd.NaT)
        # FinLab tables contain pre/post-history padding. It is not an active-period gap.
        # Tiingo returned rows are declared sessions, including boundary rows.
        window = (
            prices
            if frame.attrs.get("boundary_rows_are_sessions") or not usable_count
            else prices.loc[start:end]
        )
        missing = window.isna().any(axis=1)
        allowed = {
            pd.Timestamp(d): reason
            for d, reason in (non_trading_dates or {}).get(symbol, {}).items()
            if reason in {"market_suspension", "legitimate_non_trading"}
        }
        unexplained_dates = []
        for date in window.index[missing]:
            explained = date in allowed
            if not explained:
                unexplained_dates.append(str(date.date()))
            details.append(
                dict(
                    asset_id=symbol,
                    date=date,
                    raw_missing=bool(pd.isna(window.loc[date, "raw_close"])),
                    adjusted_missing=bool(pd.isna(window.loc[date, "adjusted_close"])),
                    reason=allowed.get(date, "unexplained_missing_price"),
                    status="EXPLAINED" if explained else "UNEXPLAINED",
                )
            )
        count = len(unexplained_dates)
        fatal = invalid > 0 or usable_count < 2 or (policy == "error" and count > 0)
        bad |= fatal
        records.append(
            dict(
                asset_id=symbol,
                ticker=symbol,
                first_valid_date=start,
                last_valid_date=end,
                missing_count=int(missing.sum()),
                unexplained_missing_count=count,
                unexpected_missing_count=count,
                explained_missing_count=int(missing.sum()) - count,
                invalid_price_count=invalid,
                validation_status="ERROR" if fatal else "WARNING" if count else "PASS",
                daily_metrics_reliable=bool(
                    not count and not invalid and usable_count >= 2
                ),
                missing_dates=";".join(str(d.date()) for d in window.index[missing]),
                unexplained_missing_dates=";".join(unexplained_dates),
                missing_data_policy=policy,
                policy="missing observations excluded explicitly; no price/return fill",
            )
        )
        if count and policy == "warn" and not fatal:
            (logger or logging.getLogger(__name__)).warning(
                "%s has %s unexplained missing observations. Continuing because MISSING_DATA_POLICY=warn. See results/missing_data_details.csv.",
                symbol,
                count,
            )
    report = pd.DataFrame(records)
    detail_report = pd.DataFrame(details, columns=DETAIL_COLUMNS)
    report.attrs["missing_data_details"] = detail_report
    if bad:
        raise DataQualityError(report, detail_report)
    return report


def gap_annotations(
    index: pd.DatetimeIndex, details: pd.DataFrame, asset_id: str
) -> pd.DataFrame:
    """Count excluded missing source sessions spanned by each observed return."""
    own = details.loc[details.asset_id == asset_id]
    rows = []
    previous = None
    for date in index:
        between = (
            own.iloc[:0]
            if previous is None
            else own.loc[(own.date > previous) & (own.date <= date)]
        )
        count = int((between.status == "UNEXPLAINED").sum())
        rows.append(
            dict(
                missing_sessions_since_previous_observation=len(between),
                unexplained_missing_sessions_since_previous_observation=count,
                spans_missing_sessions=bool(len(between)),
            )
        )
        previous = date
    return pd.DataFrame(rows, index=index)
