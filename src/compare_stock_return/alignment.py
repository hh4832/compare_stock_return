"""Global and pairwise windows retain the longer pairwise history."""

import pandas as pd


def usable(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[frame[["raw_close", "adjusted_close"]].notna().all(axis=1)]


def align(
    assets: dict, start=None, end=None, strict: bool = False, calendar: bool = False
) -> tuple[dict, dict]:
    clean = {s: usable(f) for s, f in assets.items()}
    first = max(f.index[0] for f in clean.values())
    last = min(f.index[-1] for f in clean.values())
    if strict and (
        (start is not None and pd.Timestamp(start) < first)
        or (end is not None and pd.Timestamp(end) > last)
    ):
        raise ValueError("Custom window outside an asset's available history")
    first = max(first, pd.Timestamp(start)) if start is not None else first
    last = min(last, pd.Timestamp(end)) if end is not None else last
    if calendar:
        out = {s: f.loc[first:last] for s, f in clean.items()}
        if first >= last or any(len(f) < 2 for f in out.values()):
            raise ValueError("Insufficient observations in common calendar window")
        return out, dict(
            start_date=str(first.date()),
            end_date=str(last.date()),
            observations=min(len(f) for f in out.values()),
            per_asset_observations={s: len(f) for s, f in out.items()},
            excluded_calendar_dates={s: 0 for s in out},
            boundary_policy="first/last own-market observations inside window; no fill",
        )
    dates = None
    for f in clean.values():
        idx = f.loc[first:last].index
        dates = idx if dates is None else dates.intersection(idx)
    if len(dates) < 2:
        raise ValueError("Empty/insufficient common intersection (need >=2 prices)")
    info = dict(
        start_date=str(dates[0].date()),
        end_date=str(dates[-1].date()),
        observations=len(dates),
        excluded_calendar_dates={
            s: len(f.loc[first:last]) - len(dates) for s, f in clean.items()
        },
    )
    return {s: f.loc[dates] for s, f in clean.items()}, info
