"""Distinct peak-to-recovery underwater episodes, including open episodes."""

import pandas as pd

COLUMNS = [
    "rank",
    "peak_date",
    "trough_date",
    "recovery_date",
    "max_drawdown",
    "peak_to_trough_days",
    "recovery_days",
    "total_underwater_days",
    "recovered",
]


def underwater(prices: pd.Series) -> pd.Series:
    return prices / prices.cummax() - 1


def episodes(prices: pd.Series, top: int = 10) -> pd.DataFrame:
    dd = underwater(prices)
    peak = prices.index[0]
    trough = None
    rows = []

    def record(recovery):
        last = recovery if recovery is not None else prices.index[-1]
        rows.append(
            dict(
                peak_date=peak,
                trough_date=trough,
                recovery_date=recovery,
                max_drawdown=float(dd.loc[trough]),
                peak_to_trough_days=(trough - peak).days,
                recovery_days=(recovery - trough).days
                if recovery is not None
                else None,
                total_underwater_days=(last - peak).days,
                recovered=recovery is not None,
            )
        )

    for date, value in dd.items():
        if value >= 0:
            if trough is not None:
                record(date)
                trough = None
            peak = date
        elif trough is None or value < dd.loc[trough]:
            trough = date
    if trough is not None:
        record(None)
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=COLUMNS)
    out = out.sort_values("max_drawdown").head(top).reset_index(drop=True)
    out.insert(0, "rank", range(1, len(out) + 1))
    return out[COLUMNS]
