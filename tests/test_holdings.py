import pandas as pd
import pytest

from compare_stock_return.holdings import analyze


def test_holdings(tmp_path):
    paths = {}
    for s, weights in [("A", [0.6, 0.4]), ("B", [0.5, 0.5])]:
        path = tmp_path / f"{s}.csv"
        pd.DataFrame(
            dict(
                ticker=["X", "Y"],
                weight=weights,
                as_of_date=["2020-01-01"] * 2,
                source=["test"] * 2,
            )
        ).to_csv(path, index=False)
        paths[s] = path
    stats, pairs = analyze(paths)
    assert stats.iloc[0].HHI == pytest.approx(0.52)
    assert pairs.iloc[0].weighted_overlap == pytest.approx(0.9)
