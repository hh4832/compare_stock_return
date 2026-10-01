"""Monthly rebalanced local-currency return model; no FX or actual wealth accounting."""

import numpy as np
import pandas as pd

from .cross_market import monthly_series
from .metrics import safe_ratio

LABEL = "local-currency model portfolio; FX excluded; monthly rebalancing"


def validate_weights(weights: dict, available) -> None:
    if not weights or not set(weights) <= set(available):
        raise ValueError("Portfolio contains missing/unconfigured assets")
    values = np.array(list(weights.values()), dtype=float)
    if (
        not np.isfinite(values).all()
        or (values < 0).any()
        or abs(values.sum() - 1) >= 1e-8
    ):
        raise ValueError("Portfolio weights must be finite, nonnegative and sum to 1")


def simulate(prices: dict, portfolios: dict, risk_free_rate: float = 0) -> tuple:
    metrics, months, years, navs = [], [], [], {}
    for name, weights in portfolios.items():
        validate_weights(weights, prices)
        table = pd.concat(
            {a: monthly_series(prices[a]) for a in weights}, axis=1, join="inner"
        )
        if table.empty:
            raise ValueError(f"{name}: no complete common months for portfolio")
        periods = pd.PeriodIndex(table.index, freq="M")
        if len(periods) > 1 and not (np.diff(periods.asi8) == 1).all():
            raise ValueError("Portfolio has missing months; no fill permitted")
        r = table.mul(pd.Series(weights)).sum(axis=1, min_count=len(weights))
        if r.isna().any():
            raise ValueError("Portfolio contains missing component returns")
        nav = pd.Series(
            np.r_[100, 100 * (1 + r).cumprod().to_numpy()],
            index=pd.DatetimeIndex(
                [periods[0].start_time - pd.Timedelta(days=1)]
                + list(periods.to_timestamp(how="end").normalize())
            ),
        )
        navs[name] = nav
        vol = r.std(ddof=1) * np.sqrt(12)
        excess = r - ((1 + risk_free_rate) ** (1 / 12) - 1)
        downside = np.sqrt(np.minimum(excess, 0).pow(2).mean()) * np.sqrt(12)
        growth = (nav.iloc[-1] / 100) ** (12 / len(r)) - 1
        dd = (nav / nav.cummax() - 1).min()
        annual = (1 + r).groupby(periods.year).prod() - 1
        counts = r.groupby(periods.year).size()
        complete = annual[counts == 12]
        metrics.append(
            dict(
                portfolio=name,
                accounting=LABEL,
                start_date=nav.index[0],
                end_date=nav.index[-1],
                months=len(r),
                cumulative_return=nav.iloc[-1] / 100 - 1,
                CAGR=growth,
                annualized_volatility=vol,
                maximum_drawdown=dd,
                Sharpe=safe_ratio(excess.mean() * 12, vol),
                Sortino=safe_ratio(excess.mean() * 12, downside),
                Calmar=safe_ratio(growth, abs(dd)),
                best_month=r.max(),
                worst_month=r.min(),
                best_year=complete.max(),
                worst_year=complete.min(),
                worst_rolling_12m_return=(
                    (1 + r).rolling(12).apply(np.prod, raw=True) - 1
                ).min(),
            )
        )
        months.extend(
            dict(portfolio=name, period=str(t), return_value=float(v), accounting=LABEL)
            for t, v in r.items()
        )
        years.extend(
            dict(
                portfolio=name,
                period=str(t),
                return_value=float(v),
                partial_period=bool(counts[t] != 12),
                accounting=LABEL,
            )
            for t, v in annual.items()
        )
    return (
        pd.DataFrame(metrics, columns=None if metrics else ["portfolio", "accounting"]),
        pd.DataFrame(
            months,
            columns=None
            if months
            else ["portfolio", "period", "return_value", "accounting"],
        ),
        pd.DataFrame(
            years,
            columns=None
            if years
            else [
                "portfolio",
                "period",
                "return_value",
                "partial_period",
                "accounting",
            ],
        ),
        navs,
    )
