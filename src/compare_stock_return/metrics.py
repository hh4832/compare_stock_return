"""Central numerical definitions. Ratios with undefined denominators are NaN."""

import numpy as np
import pandas as pd

from .config import TRADING_DAYS
from .drawdown import episodes
from .returns import daily_returns


def cagr(prices: pd.Series) -> float:
    days = (prices.index[-1] - prices.index[0]).days
    return (
        float((prices.iloc[-1] / prices.iloc[0]) ** (365.25 / days) - 1)
        if days
        else np.nan
    )


def safe_ratio(a: float, b: float) -> float:
    return float(a / b) if np.isfinite(b) and b > 0 else np.nan


def calendar_returns(prices: pd.Series, frequency: str) -> pd.DataFrame:
    r = daily_returns(prices).iloc[1:]
    period = r.index.to_period(frequency)
    result = (1 + r).groupby(period).prod() - 1
    rows = []
    for key, value in result.items():
        # Conservative boundary label, never assert complete boundary periods.
        partial = key.start_time <= prices.index[0] or key.end_time >= prices.index[-1]
        rows.append(
            dict(
                period=str(key), return_value=float(value), partial_period=bool(partial)
            )
        )
    return pd.DataFrame(rows, columns=["period", "return_value", "partial_period"])


def summary(prices: pd.Series, risk_free_rate: float = 0) -> dict:
    r = daily_returns(prices).iloc[1:]
    rf = (1 + risk_free_rate) ** (1 / TRADING_DAYS) - 1
    excess = r - rf
    vol = float(r.std(ddof=1) * np.sqrt(TRADING_DAYS))
    downside = float(
        np.sqrt(np.mean(np.minimum(excess, 0) ** 2)) * np.sqrt(TRADING_DAYS)
    )
    dd = episodes(prices)
    worst = dd.iloc[0] if len(dd) else None
    growth = cagr(prices)
    mdd = float(worst.max_drawdown) if worst is not None else 0.0
    annual, monthly = calendar_returns(prices, "Y"), calendar_returns(prices, "M")
    completed = annual.loc[~annual.partial_period]
    from .rolling import rolling_return

    rr = rolling_return(prices, 12)
    return dict(
        start_date=prices.index[0],
        end_date=prices.index[-1],
        number_of_trading_days=len(prices),
        return_observations=len(r),
        cumulative_return=float(prices.iloc[-1] / prices.iloc[0] - 1),
        CAGR=growth,
        annualized_volatility=vol,
        maximum_drawdown=mdd,
        maximum_drawdown_start=worst.peak_date if worst is not None else None,
        maximum_drawdown_trough=worst.trough_date if worst is not None else None,
        maximum_drawdown_recovery=worst.recovery_date if worst is not None else None,
        drawdown_duration=worst.total_underwater_days if worst is not None else 0,
        recovery_duration=worst.recovery_days if worst is not None else None,
        Sharpe=safe_ratio(excess.mean() * TRADING_DAYS, vol),
        Sortino=safe_ratio(excess.mean() * TRADING_DAYS, downside),
        Calmar=safe_ratio(growth, abs(mdd)),
        best_calendar_year=completed.return_value.max(),
        worst_calendar_year=completed.return_value.min(),
        best_month=monthly.return_value.max(),
        worst_month=monthly.return_value.min(),
        worst_rolling_12m_return=rr.min(),
        annualization_warning=(prices.index[-1] - prices.index[0]).days < 365,
        short_sample_warning=len(prices) < 60,
    )
