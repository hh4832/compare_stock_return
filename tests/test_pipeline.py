import json

import pandas as pd
import pytest

from compare_stock_return.config import Config
from compare_stock_return.pipeline import run


def test_end_to_end_and_failure_preserves_latest(tmp_path, assets):
    c = Config(
        symbols=["A", "B"],
        benchmark="A",
        drive_output_root=str(tmp_path),
        progress=False,
        display_symbols=["A"],
        missing_data_policy="error",
    )
    result = run(c, assets)
    path = result["run_path"]
    assert result["metadata"]["status"] == "SUCCESS"
    assert (path / "charts/rolling_sharpe.png").exists()
    assert set(pd.read_csv(path / "results/summary_metrics.csv").ticker) == {"A", "B"}
    latest = (tmp_path / "latest/metadata/run_metadata.json").read_bytes()
    broken = {s: f.copy() for s, f in assets.items()}
    broken["A"].iloc[30, 0] = float("nan")
    with pytest.raises(ValueError):
        run(c, broken)
    assert (tmp_path / "latest/metadata/run_metadata.json").read_bytes() == latest
    failed = [p for p in (tmp_path / "runs").iterdir() if p != path][0]
    assert (
        json.loads((failed / "metadata/run_metadata.json").read_text())["status"]
        == "FAILED"
    )
    assert (failed / "results/data_quality_report.csv").exists()


def test_pairwise_longer_than_global(tmp_path, assets):
    assets["C"] = assets["B"].iloc[40:].copy()
    c = Config(
        symbols=["A", "B", "C"],
        benchmark="A",
        drive_output_root=str(tmp_path),
        progress=False,
        display_symbols=[],
    )
    out = run(c, assets)
    pair = pd.read_csv(out["run_path"] / "results/pairwise_metrics.csv")
    assert (
        pair.loc[(pair.asset_a == "A") & (pair.asset_b == "B"), "observations"].iloc[0]
        == 80
    )
    assert out["metadata"]["common_comparison_range"]["observations"] == 40


@pytest.mark.parametrize("mode", ["full_history", "custom"])
def test_modes(tmp_path, assets, mode):
    c = Config(
        symbols=["A", "B"],
        benchmark="A",
        drive_output_root=str(tmp_path),
        progress=False,
        display_symbols=[],
        date_mode=mode,
        custom_start_date="2020-03-01",
        custom_end_date="2020-04-01",
    )
    out = run(c, assets)
    if mode == "full_history":
        assert out["summary_metrics"].number_of_trading_days.tolist() == [100, 80]
    else:
        assert out["summary_metrics"].start_date.min() >= pd.Timestamp("2020-03-01")
