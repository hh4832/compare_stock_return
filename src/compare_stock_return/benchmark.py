"""Pairwise price alignment before computing returns, never join stale returns."""

import numpy as np
import pandas as pd
from scipy import stats

from .metrics import calendar_returns, safe_ratio, summary
from .regression import fit


def relative(a: pd.Series, b: pd.Series, risk_free_rate: float = 0) -> dict:
    joined = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()
    if len(joined) < 2:
        raise ValueError("Insufficient pairwise common observations")
    r = joined.pct_change(fill_method=None).iloc[1:]
    excess = r.a - r.b
    te = float(excess.std() * np.sqrt(252))
    rf = (1 + risk_free_rate) ** (1 / 252) - 1
    sa, sb = summary(joined.a, risk_free_rate), summary(joined.b, risk_free_rate)
    ma, mb = calendar_returns(joined.a, "M"), calendar_returns(joined.b, "M")
    monthly = ma.merge(mb, on="period", suffixes=("_a", "_b"))
    complete = monthly.loc[~(monthly.partial_period_a | monthly.partial_period_b)]
    mex = complete.return_value_a - complete.return_value_b

    def capture(mask):
        aa = (1 + r.a[mask]).prod() - 1
        bb = (1 + r.b[mask]).prod() - 1
        return float(aa / bb) if mask.any() and bb != 0 else np.nan

    result = dict(
        start_date=joined.index[0],
        end_date=joined.index[-1],
        observations=len(joined),
        excluded_dates_a=len(a) - len(joined),
        excluded_dates_b=len(b) - len(joined),
        cumulative_excess_return=sa["cumulative_return"] - sb["cumulative_return"],
        annualized_excess_return=float(excess.mean() * 252),
        excess_CAGR=sa["CAGR"] - sb["CAGR"],
        correlation=r.a.corr(r.b),
        tracking_error=te,
        information_ratio=safe_ratio(excess.mean() * 252, te),
        upside_capture=capture(r.b > 0),
        downside_capture=capture(r.b < 0),
        monthly_excess_mean=mex.mean(),
        monthly_excess_median=mex.median(),
        monthly_excess_std=mex.std(),
        positive_month_ratio=(mex > 0).mean() if len(mex) else np.nan,
        monthly_excess_t_statistic=float(stats.ttest_1samp(mex, 0).statistic)
        if len(mex) > 1 and mex.std() > 0
        else np.nan,
        complete_months=len(mex),
        monthly_excess_returns=monthly.assign(
            excess_return=monthly.return_value_a - monthly.return_value_b
        ),
    )
    result.update(fit(r.a - rf, r.b - rf))
    for label, metrics in [("asset_a", sa), ("asset_b", sb)]:
        for name, source in [
            ("cagr", "CAGR"),
            ("mdd", "maximum_drawdown"),
            ("cumulative_return", "cumulative_return"),
            ("volatility", "annualized_volatility"),
            ("sharpe", "Sharpe"),
        ]:
            result[f"{label}_{name}"] = metrics[source]
    result["cagr_difference"] = result["excess_CAGR"]
    return result
