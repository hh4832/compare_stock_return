import numpy as np
import pandas as pd

from compare_stock_return.alignment import align
from compare_stock_return.config import Config
from compare_stock_return.pipeline import run
from compare_stock_return.validation import validate_assets


def frame(dates):
    values = 100 * np.exp(
        np.arange(len(dates)) * 0.001 + np.sin(np.arange(len(dates))) * 0.005
    )
    return pd.DataFrame(dict(raw_close=values, adjusted_close=values), index=dates)


def test_holidays_counts_and_common():
    dates = pd.bdate_range("2020-01-01", "2021-03-31")
    assets = {
        "TW:0050": frame(dates.delete([5, 10])),
        "US:VOO": frame(dates.delete([7])),
    }
    validate_assets(assets)
    out, info = align(assets, calendar=True)
    assert info["start_date"] == "2020-01-01"
    assert len(out["TW:0050"]) != len(out["US:VOO"])
    assert dates[7] in out["TW:0050"].index
    assert dates[5] in out["US:VOO"].index


def test_pipeline_routing_and_outputs(tmp_path, monkeypatch):
    import compare_stock_return.pipeline as pipeline
    from compare_stock_return.benchmark import relative

    dates = pd.bdate_range("2020-01-01", "2022-03-31")
    assets = {
        "TW:0050": frame(dates.delete([5])),
        "US:VOO": frame(dates.delete([7, 10])),
        "US:VGT": frame(dates.delete([7, 10])),
    }
    called = []

    def guarded(a, b, rf):
        called.append(1)
        return relative(a, b, rf)

    monkeypatch.setattr(pipeline, "relative", guarded)
    monkeypatch.setenv("TIINGO_API_TOKEN", "secret-never-save")
    c = Config(
        assets=list(assets),
        benchmark="TW:0050",
        drive_output_root=str(tmp_path),
        progress=False,
        display_symbols=[],
        portfolios={"mix": {"TW:0050": 0.3, "US:VOO": 0.5, "US:VGT": 0.2}},
    )
    result = run(c, assets)
    assert len(called) == 1  # US pair only, no cross-market daily benchmarks
    pair = pd.read_csv(result["run_path"] / "results/pairwise_metrics.csv")
    assert set(pair.comparison_type) == {"same_market_daily", "cross_market_monthly"}
    cross = pair[pair.comparison_type == "cross_market_monthly"]
    assert cross.beta.isna().all()
    for name in [
        "cross_market_monthly_metrics.csv",
        "model_portfolio_metrics.csv",
        "model_portfolio_monthly_returns.csv",
        "model_portfolio_annual_returns.csv",
    ]:
        assert (result["run_path"] / "results" / name).exists()
    assert (result["run_path"] / "data/corporate_actions.parquet").exists()
    for path in result["run_path"].rglob("*"):
        if path.is_file():
            assert b"secret-never-save" not in path.read_bytes()
