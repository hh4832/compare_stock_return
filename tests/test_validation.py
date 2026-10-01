import numpy as np
import pytest

from compare_stock_return.config import Config
from compare_stock_return.symbol_resolver import resolve
from compare_stock_return.validation import DataQualityError, validate_assets


@pytest.mark.parametrize(
    "kwargs",
    [
        {"symbols": ["A", "A"], "benchmark": "A"},
        {"date_mode": "bad"},
        {"return_type": "bad"},
        {
            "date_mode": "custom",
            "custom_start_date": "oops",
            "custom_end_date": "2020-01-01",
        },
        {"symbols": []},
        {"benchmark": "MISSING"},
    ],
)
def test_invalid_config(kwargs):
    with pytest.raises((ValueError, TypeError)):
        Config(**kwargs).validate()


def test_missing(assets):
    assets["A"].iloc[30, 0] = np.nan
    with pytest.raises(DataQualityError) as error:
        validate_assets(assets, policy="error")
    assert error.value.report.iloc[0].unexpected_missing_count == 1
    date = str(assets["A"].index[30].date())
    report = validate_assets(assets, {"A": {date: "market_suspension"}})
    assert report.iloc[0].explained_missing_count == 1


def test_no_asset():
    with pytest.raises(ValueError):
        resolve(["bad"], ["A"])
