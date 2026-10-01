import pytest

from compare_stock_return.alignment import align


def test_intersection(assets):
    out, info = align(assets)
    assert len(out["A"]) == 80
    assert out["A"].index.equals(out["B"].index)
    assert info["start_date"] == str(assets["B"].index[0].date())


def test_custom(assets):
    out, _ = align(assets, "2020-01-01", "2020-03-01", False)
    assert out["A"].index[0] == assets["B"].index[0]
    with pytest.raises(ValueError):
        align(assets, "2020-01-01", "2020-03-01", True)


def test_empty(assets):
    with pytest.raises(ValueError):
        align(assets, "2030-01-01", "2030-02-01")
