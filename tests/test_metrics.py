import numpy as np
import pandas as pd
import pytest

from compare_stock_return.fees import synthetic_fee_adjusted
from compare_stock_return.metrics import cagr, calendar_returns, summary


def test_cagr_calendar():
    p = pd.Series([100, 120], index=pd.to_datetime(["2020-01-01", "2021-01-01"]))
    assert cagr(p) == pytest.approx(1.2 ** (365.25 / 366) - 1)


def test_risk_formulas():
    p = pd.Series([100, 110, 99, 108], index=pd.date_range("2020-01-01", periods=4))
    r = np.array([0.1, -0.1, 108 / 99 - 1])
    m = summary(p)
    assert m["annualized_volatility"] == pytest.approx(r.std(ddof=1) * np.sqrt(252))
    assert m["Sharpe"] == pytest.approx(r.mean() / r.std(ddof=1) * np.sqrt(252))
    assert m["Sortino"] == pytest.approx(
        r.mean() / np.sqrt(np.mean(np.minimum(r, 0) ** 2)) * np.sqrt(252)
    )
    assert m["maximum_drawdown"] == pytest.approx(-0.1)
    assert m["Calmar"] == pytest.approx(cagr(p) / 0.1)


def test_constant():
    p = pd.Series([100] * 5, index=pd.date_range("2020-01-01", periods=5))
    m = summary(p)
    assert m["maximum_drawdown"] == 0
    assert np.isnan(m["Sharpe"]) and np.isnan(m["Calmar"])


def test_partial_period():
    p = pd.Series(np.arange(800) + 100, index=pd.date_range("2020-03-01", periods=800))
    annual = calendar_returns(p, "Y")
    assert annual.partial_period.tolist() == [True, False, True]


def test_fee():
    p = pd.Series([100, 100], index=pd.to_datetime(["2020-01-01", "2021-01-01"]))
    assert synthetic_fee_adjusted(p, 0.01).iloc[-1] == pytest.approx(
        100 * 0.99 ** (366 / 365.25)
    )
    with pytest.raises(ValueError):
        synthetic_fee_adjusted(p, 0.01, True)
