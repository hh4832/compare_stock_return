import pandas as pd
import pytest

from compare_stock_return.drawdown import episodes, underwater


def test_recovered_open():
    p = pd.Series(
        [100, 120, 90, 120, 130, 100], index=pd.date_range("2020-01-01", periods=6)
    )
    d = episodes(p)
    assert len(d) == 2
    assert d.iloc[0].max_drawdown == pytest.approx(-0.25)
    assert bool(d.iloc[0].recovered)
    assert d.iloc[0].peak_to_trough_days == 1
    assert d.iloc[0].recovery_days == 1
    assert not bool(d.iloc[1].recovered)
    assert pd.isna(d.iloc[1].recovery_date)
    assert underwater(p).min() == pytest.approx(-0.25)


def test_no_drawdown():
    p = pd.Series([1, 2, 3], index=pd.date_range("2020-01-01", periods=3))
    assert episodes(p).empty
