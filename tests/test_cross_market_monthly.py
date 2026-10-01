import numpy as np
import pandas as pd
import pytest

from compare_stock_return.cross_market import monthly_metrics, monthly_series


def test_monthly_correlation():
    dates = pd.date_range("2020-01-01", "2022-04-01")
    values = 100 * np.exp(
        np.arange(len(dates)) * 0.001 + np.sin(np.arange(len(dates)) * 0.02) * 0.03
    )
    a = pd.Series(values, index=dates)
    result = monthly_metrics(a, a * 2)
    assert result["monthly_correlation"] == pytest.approx(1)
    assert result["monthly_covariance"] == pytest.approx(monthly_series(a).var())
    assert "beta" not in result
    assert result["complete_months"] == 26
