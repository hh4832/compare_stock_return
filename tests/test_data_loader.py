import json
import sys
import types

import pytest

from compare_stock_return import data_loader
from compare_stock_return.config import Config


def test_fresh_cache_refresh_and_expiry(tmp_path, assets, monkeypatch):
    calls = []

    def get(dataset, **kwargs):
        calls.append((dataset, kwargs))
        if dataset == "security_categories":
            import pandas as pd

            return pd.DataFrame(
                dict(stock_id=["A", "B"], name=["Alpha", "Beta"], market=["sii", "etf"])
            )
        column = "raw_close" if dataset == "price:收盤價" else "adjusted_close"
        import pandas as pd

        return pd.concat({s: f[column] for s, f in assets.items()}, axis=1)

    monkeypatch.setattr(data_loader, "authenticate", lambda: None)
    monkeypatch.setitem(
        sys.modules,
        "finlab",
        types.SimpleNamespace(data=types.SimpleNamespace(get=get)),
    )
    c = Config(symbols=["A", "B"], benchmark="A")
    _, names, _ = data_loader.load(c, tmp_path)
    assert names["B"]["type"] == "ETF"
    assert all(
        kwargs.get("force_download")
        for ds, kwargs in calls
        if ds != "security_categories"
    )
    calls.clear()
    _, _, provenance = data_loader.load(c, tmp_path)
    assert provenance["raw_close"]["cache_hit"]
    assert len(calls) == 1
    for path in tmp_path.glob("*.json"):
        info = json.loads(path.read_text())
        info["downloaded_at"] = "2000-01-01T00:00:00+00:00"
        path.write_text(json.dumps(info))
    calls.clear()
    data_loader.load(c, tmp_path)
    assert len(calls) == 3
    calls.clear()
    c.refresh_cache = True
    data_loader.load(c, tmp_path)
    assert len(calls) == 3


def test_missing_auth(monkeypatch):
    monkeypatch.delenv("FINLAB_API_TOKEN", raising=False)
    monkeypatch.setitem(sys.modules, "google.colab", None)
    with pytest.raises(data_loader.AuthenticationError):
        data_loader.authenticate()


def test_prefixed_finlab_contract_and_cache_directory(tmp_path, assets, monkeypatch):
    from compare_stock_return.providers import legacy_finlab
    from compare_stock_return.providers.finlab_provider import FinLabProvider

    calls = []

    def fake(config, cache):
        calls.append((config.symbols, cache))
        return (
            {"0050": assets["A"]},
            {"0050": {"name": "Test", "type": "ETF"}},
            {"dataset": "etl:adj_close"},
        )

    monkeypatch.setattr(legacy_finlab, "load", fake)
    config = Config(assets=["TW:0050"], benchmark="TW:0050")
    frames, metadata, provenance = FinLabProvider().load(
        config, config.assets, tmp_path / "finlab"
    )
    assert frames["TW:0050"].equals(assets["A"])
    assert metadata["TW:0050"]["currency"] == "TWD"
    assert calls[0][0] == ["0050"]
    assert provenance["dataset"] == "etl:adj_close"


def test_known_suspension_kept():
    config = Config(assets=["TW:0050"], benchmark="TW:0050")
    config.validate()
    assert len(config.non_trading_dates["TW:0050"]) == 5
    assert set(config.non_trading_dates["TW:0050"].values()) == {"market_suspension"}
