"""Calendar-month return horizons; risk windows use explicit 21 sessions/month."""

import numpy as np
import pandas as pd

from .config import TRADING_DAYS
from .returns import daily_returns


def rolling_return(
    prices: pd.Series, months: int, annualized: bool = False
) -> pd.Series:
    dates = prices.index - pd.DateOffset(months=months)
    positions = prices.index.searchsorted(dates, side="right") - 1
    out = pd.Series(np.nan, index=prices.index, dtype=float)
    valid = positions >= 0
    out.iloc[np.flatnonzero(valid)] = (
        prices.iloc[np.flatnonzero(valid)].to_numpy()
        / prices.iloc[positions[valid]].to_numpy()
        - 1
    )
    if annualized:
        actual_days = (prices.index[valid] - prices.index[positions[valid]]).days
        out.iloc[np.flatnonzero(valid)] = (1 + out.iloc[np.flatnonzero(valid)]) ** (
            365.25 / actual_days
        ) - 1
    return out


def rolling_metrics(prices: pd.Series, risk_free_rate: float = 0) -> pd.DataFrame:
    out = pd.DataFrame(index=prices.index)
    for months in [1, 3, 6, 12, 36, 60]:
        out[f"return_{months}m"] = rolling_return(prices, months, months >= 36)
    r = daily_returns(prices)
    for months in [12, 36]:
        window = months * 21
        out[f"volatility_{months}m"] = r.rolling(
            window, min_periods=window
        ).std() * np.sqrt(TRADING_DAYS)
    excess = r - ((1 + risk_free_rate) ** (1 / TRADING_DAYS) - 1)
    out["Sharpe_36m"] = (
        excess.rolling(756).mean()
        * TRADING_DAYS
        / out.volatility_36m.replace(0, np.nan)
    )
    out["maximum_drawdown_12m"] = prices.rolling(252, min_periods=252).apply(
        lambda x: (x / np.maximum.accumulate(x) - 1).min(), raw=True
    )
    return out
