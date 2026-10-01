import pytest

from compare_stock_return.asset_id import parse_asset_id
from compare_stock_return.config import Config


def test_identifiers():
    assert parse_asset_id("TW:0050").symbol == "0050"
    assert parse_asset_id("US:VOO").currency == "USD"


@pytest.mark.parametrize(
    "value", ["0050", "EU:ABC", "US:", "US: A", "us:VOO", "TW:0050:extra", 123]
)
def test_reject(value):
    with pytest.raises(ValueError):
        parse_asset_id(value)


def test_fx():
    with pytest.raises(NotImplementedError):
        Config(fx_mode="twd").validate()
