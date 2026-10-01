import json

import pytest

from compare_stock_return.config import Config
from compare_stock_return.providers.tiingo_provider import TiingoProvider, normalize
from compare_stock_return.returns import return_columns
from compare_stock_return.validation import DataQualityError


@pytest.fixture
def rows():
    return [
        dict(date=d, close=c, adjClose=100, divCash=v, splitFactor=s)
        for d, c, v, s in [
            ("2024-01-02T00:00:00Z", 100, 0, 1),
            ("2024-01-03T00:00:00Z", 90, 10, 1),
            ("2024-01-04T00:00:00Z", 45, 0, 2),
        ]
    ]


def test_mapping_no_double_count(rows):
    f = normalize(rows)
    assert f.raw_close.tolist() == [100, 90, 45]
    assert f.splitFactor.tolist() == [1, 1, 2]
    assert f.divCash.sum() == 10
    assert return_columns(f).total_return.iloc[1:].eq(0).all()


@pytest.mark.parametrize(
    "column,index", [("close", 1), ("adjClose", 1), ("close", 0), ("adjClose", 2)]
)
def test_gap_fatal(rows, column, index):
    rows[index][column] = None
    with pytest.raises(DataQualityError):
        normalize(rows, policy="error")


def test_duplicate_order_invalid(rows):
    with pytest.raises(ValueError):
        normalize(rows[::-1])
    with pytest.raises(ValueError):
        normalize(rows + [rows[-1]])


def test_cache_credentials_and_refresh(tmp_path, rows, monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return rows

    class Session:
        def get(self, url, **kwargs):
            calls.append(kwargs)
            return Response()

    monkeypatch.setenv("TIINGO_API_TOKEN", "secret-never-save")
    provider = TiingoProvider(Session())
    c = Config(assets=["US:VOO"], benchmark="US:VOO")
    _, _, provenance = provider.load(c, c.assets, tmp_path)
    assert not provenance["US:VOO"]["cache_hit"]
    _, _, provenance = provider.load(c, c.assets, tmp_path)
    assert provenance["US:VOO"]["cache_hit"] and len(calls) == 1
    assert "secret-never-save" not in json.dumps(provenance)
    for path in tmp_path.glob("*.json"):
        assert "secret-never-save" not in path.read_text()
        info = json.loads(path.read_text())
        info["downloaded_at"] = "2000-01-01T00:00:00+00:00"
        path.write_text(json.dumps(info))
    provider.load(c, c.assets, tmp_path)
    c.refresh_cache = True
    provider.load(c, c.assets, tmp_path)
    assert len(calls) == 3
    assert "token" not in calls[0]["params"]


def test_exception_payload_sanitized(tmp_path, monkeypatch):
    class Session:
        def get(self, *a, **kw):
            raise RuntimeError("secret-never-save")

    monkeypatch.setenv("TIINGO_API_TOKEN", "secret-never-save")
    with pytest.raises(RuntimeError) as e:
        TiingoProvider(Session()).load(Config(), ["US:VOO"], tmp_path)
    assert "secret-never-save" not in str(e.value)
