"""Monthly calendar alignment, using complete months only and no daily synchronization."""

import numpy as np
import pandas as pd

from .metrics import calendar_returns


def monthly_series(prices: pd.Series) -> pd.Series:
    records = calendar_returns(prices, "M")
    records = records.loc[~records.partial_period]
    return records.set_index("period").return_value


def monthly_metrics(a: pd.Series, b: pd.Series) -> dict:
    joined = pd.concat(
        [monthly_series(a).rename("a"), monthly_series(b).rename("b")],
        axis=1,
        join="inner",
    ).dropna()
    return dict(
        comparison_type="cross_market_monthly",
        daily_alignment_status="CROSS_MARKET_DAILY_ALIGNMENT_NOT_IMPLEMENTED",
        complete_months=len(joined),
        monthly_correlation=joined.a.corr(joined.b) if len(joined) > 1 else np.nan,
        monthly_covariance=joined.a.cov(joined.b) if len(joined) > 1 else np.nan,
        positive_month_co_movement=((joined.a > 0) & (joined.b > 0)).mean()
        if len(joined)
        else np.nan,
        downside_month_co_movement=((joined.a < 0) & (joined.b < 0)).mean()
        if len(joined)
        else np.nan,
    )
