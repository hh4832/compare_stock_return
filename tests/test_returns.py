import numpy as np
import pandas as pd
import pytest

from compare_stock_return.returns import daily_returns, equity, return_columns


def test_no_fill():
    p = pd.Series([100, np.nan, 110, 121])
    r = daily_returns(p)
    assert r.iloc[:3].isna().all()
    assert r.iloc[3] == pytest.approx(0.1)


def test_adjusted_dividend_split():
    f = pd.DataFrame({"raw_close": [100, 90, 45], "adjusted_close": [100, 100, 100]})
    r = return_columns(f)
    assert (r.total_return.iloc[1:] == 0).all()
    assert r.price_return.iloc[1] == pytest.approx(-0.1)
    assert r.price_return.iloc[2] == pytest.approx(-0.5)


def test_equity():
    assert equity(pd.Series([50, 55, 60])).tolist() == [100, 110, 120]
