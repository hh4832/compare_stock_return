import numpy as np
import pandas as pd
import pytest

from compare_stock_return.benchmark import relative


def test_pairwise_and_tracking(assets):
    a = assets["A"].adjusted_close
    b = assets["B"].adjusted_close
    m = relative(a, b)
    p = pd.concat([a, b], axis=1, join="inner").pct_change(fill_method=None).iloc[1:]
    diff = p.iloc[:, 0] - p.iloc[:, 1]
    assert m["observations"] == 80
    assert m["excluded_dates_a"] == 20
    assert m["tracking_error"] == pytest.approx(diff.std() * np.sqrt(252))
    assert m["information_ratio"] == pytest.approx(
        diff.mean() * 252 / m["tracking_error"]
    )


def test_prices_aligned_before_return():
    dates = pd.date_range("2020-01-01", periods=4)
    a = pd.Series([100, 110, 121, 133.1], index=dates)
    b = pd.Series([100, 121, 133.1], index=dates[[0, 2, 3]])
    assert relative(a, b)["tracking_error"] == pytest.approx(0)
