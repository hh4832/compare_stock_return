import numpy as np
import pandas as pd
import pytest

from compare_stock_return.rolling import rolling_metrics, rolling_return


def test_insufficient():
    p = pd.Series(range(100, 110), index=pd.bdate_range("2020-01-01", periods=10))
    assert rolling_metrics(p).return_12m.isna().all()
    assert rolling_metrics(p).Sharpe_36m.isna().all()


def test_calendar_horizon():
    dates = pd.date_range("2020-01-01", periods=1900)
    p = pd.Series(np.exp(np.arange(1900) * 0.001), index=dates)
    r = rolling_return(p, 12)
    assert r.loc["2021-01-01"] == pytest.approx(np.exp(0.366) - 1)
    assert rolling_return(p, 36, True).iloc[-1] == pytest.approx(np.exp(0.36525) - 1)
