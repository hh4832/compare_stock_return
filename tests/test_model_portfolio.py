import numpy as np
import pandas as pd
import pytest

from compare_stock_return.model_portfolio import simulate, validate_weights


@pytest.mark.parametrize(
    "weights", [{"A": 0.9}, {"A": -1, "B": 2}, {"A": float("nan")}, {"C": 1}, {}]
)
def test_invalid_weights(weights):
    with pytest.raises(ValueError):
        validate_weights(weights, ["A", "B"])


def test_weighted_returns_and_risk():
    dates = pd.to_datetime(
        ["2019-12-31", "2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30"]
    )
    a = pd.Series([100, 110, 99, 118.8, 118.8], index=dates)
    b = pd.Series([100, 100, 110, 110, 110], index=dates)
    m, r, y, nav = simulate({"A": a, "B": b}, {"mix": {"A": 0.4, "B": 0.6}})
    assert r.return_value.to_numpy() == pytest.approx([0.04, 0.02, 0.08])
    expected = np.array([0.04, 0.02, 0.08])
    assert m.iloc[0].annualized_volatility == pytest.approx(
        expected.std(ddof=1) * np.sqrt(12)
    )
    assert nav["mix"].iloc[-1] == pytest.approx(100 * np.prod(1 + expected))
    assert m.iloc[0].CAGR == pytest.approx(np.prod(1 + expected) ** 4 - 1)
    assert "FX excluded" in m.iloc[0].accounting


def test_insufficient_months():
    a = pd.Series([100, 101], index=pd.to_datetime(["2020-01-01", "2020-01-02"]))
    with pytest.raises(ValueError):
        simulate({"A": a}, {"all": {"A": 1}})
