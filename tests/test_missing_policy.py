import json

import numpy as np
import pandas as pd
import pytest

from compare_stock_return.config import Config
from compare_stock_return.pipeline import run
from compare_stock_return.providers.tiingo_provider import normalize
from compare_stock_return.returns import daily_returns
from compare_stock_return.validation import (
    DAILY_WARNING,
    DataQualityError,
    validate_assets,
)


@pytest.fixture
def missing_assets(assets):
    assets = {"TW:0050": assets["A"].copy(), "TW:0056": assets["B"].copy()}
    assets["TW:0050"].iloc[30, 0] = np.nan
    assets["TW:0050"].iloc[31, 1] = np.nan
    return assets


def config(tmp_path, policy):
    return Config(
        assets=["TW:0050", "TW:0056"],
        benchmark="TW:0050",
        missing_data_policy=policy,
        drive_output_root=str(tmp_path),
        progress=False,
        display_symbols=[],
    )


def test_default_and_invalid_policy():
    assert Config().missing_data_policy == "warn"
    with pytest.raises(ValueError):
        Config(missing_data_policy="fill").validate()


def test_error_reports_and_metadata(tmp_path, missing_assets):
    with pytest.raises(DataQualityError) as e:
        run(config(tmp_path, "error"), missing_assets)
    assert e.value.report.iloc[0].validation_status == "ERROR"
    path = next((tmp_path / "runs").iterdir())
    assert len(pd.read_csv(path / "results/missing_data_details.csv")) == 2
    meta = json.loads((path / "metadata/run_metadata.json").read_text())
    assert meta["missing_data_policy"] == "error"
    assert meta["missing_data_by_asset"][0]["unexplained_missing_count"] == 2
    assert not (tmp_path / "latest").exists()


@pytest.mark.parametrize("policy", ["warn", "ignore"])
def test_pipeline_continues_with_audit_and_flags(tmp_path, missing_assets, policy):
    before = {a: f.copy(deep=True) for a, f in missing_assets.items()}
    out = run(config(tmp_path, policy), missing_assets)
    path = out["run_path"]
    assert out["metadata"]["status"] == "SUCCESS"
    assert out["metadata"]["data_quality_status"] == "WARNING"
    assert out["metadata"]["missing_data_policy"] == policy
    detail = pd.read_csv(path / "results/missing_data_details.csv")
    assert detail.status.tolist() == ["UNEXPLAINED", "UNEXPLAINED"]
    assert detail.raw_missing.tolist() == [True, False]
    assert detail.adjusted_missing.tolist() == [False, True]
    quality = pd.read_csv(path / "results/data_quality_report.csv").set_index(
        "asset_id"
    )
    assert quality.loc["TW:0050", "unexplained_missing_count"] == 2
    assert quality.loc["TW:0050", "validation_status"] == "WARNING"
    assert not quality.loc["TW:0050", "daily_metrics_reliable"]
    for filename in [
        "summary_metrics",
        "intersection_metrics",
        "full_history_metrics",
        "pairwise_metrics",
        "benchmark_metrics",
        "rolling_metrics",
    ]:
        table = pd.read_csv(path / f"results/{filename}.csv")
        assert DAILY_WARNING in set(table.daily_metrics_status)
    pair = pd.read_csv(path / "results/pairwise_metrics.csv").iloc[0]
    assert pair.excluded_missing_sessions_a == 2
    assert pair.unexplained_missing_sessions_a == 2
    assert len(pair.missing_dates_a.split(";")) == 2
    returns = pd.read_parquet(path / "data/returns.parquet").xs("TW:0050")
    next_date = missing_assets["TW:0050"].index[32]
    assert (
        returns.loc[
            next_date, "unexplained_missing_sessions_since_previous_observation"
        ]
        == 2
    )
    assert returns.loc[next_date, "spans_missing_sessions"]
    raw = pd.read_parquet(path / "data/source_prices.parquet").xs("TW:0050")
    assert pd.isna(raw.iloc[30].raw_close) and pd.isna(raw.iloc[31].adjusted_close)
    for asset in before:
        pd.testing.assert_frame_equal(before[asset], missing_assets[asset])
    log = (path / "logs/run.log").read_text()
    assert ("Continuing because MISSING_DATA_POLICY=warn" in log) == (policy == "warn")
    assert np.isnan(daily_returns(raw.raw_close).iloc[30])
    # Allowed endpoint metrics are computed, and raw missing values are never filled.
    summary = out["summary_metrics"].set_index("ticker")
    assert np.isfinite(summary.loc["TW:0050", "CAGR"])
    assert np.isfinite(summary.loc["TW:0050", "maximum_drawdown"])
    assert (tmp_path / "latest/results/missing_data_details.csv").exists()


@pytest.mark.parametrize("policy", ["warn", "ignore", "error"])
@pytest.mark.parametrize("value", [0, -1, np.inf, -np.inf])
def test_invalid_price_always_fatal(missing_assets, policy, value):
    missing_assets["TW:0050"].iloc[20, 0] = value
    with pytest.raises(DataQualityError):
        validate_assets(missing_assets, policy=policy)


def test_invalid_opposite_missing_at_boundary_is_fatal(missing_assets):
    missing_assets["TW:0050"].iloc[0] = [np.nan, -1]
    with pytest.raises(DataQualityError):
        validate_assets(missing_assets, policy="ignore")


@pytest.mark.parametrize("policy", ["warn", "ignore", "error"])
def test_entire_asset_missing(missing_assets, policy):
    missing_assets["TW:0050"].iloc[:, :] = np.nan
    with pytest.raises(DataQualityError):
        validate_assets(missing_assets, policy=policy)


@pytest.mark.parametrize("malformed", ["duplicate", "nat", "string"])
def test_index_fatal(missing_assets, malformed):
    frame = missing_assets["TW:0050"]
    if malformed == "duplicate":
        frame.index = pd.DatetimeIndex([frame.index[0]] * len(frame))
    elif malformed == "nat":
        frame.index = pd.DatetimeIndex([pd.NaT] * len(frame))
    else:
        frame.index = frame.index.astype(str)
    with pytest.raises(ValueError):
        validate_assets(missing_assets, policy="ignore")


def test_explained_and_unexplained_details(missing_assets):
    asset = "TW:0050"
    date = str(missing_assets[asset].index[30].date())
    quality = validate_assets(
        missing_assets, {asset: {date: "market_suspension"}}, policy="ignore"
    )
    assert quality.iloc[0].explained_missing_count == 1
    assert quality.iloc[0].unexplained_missing_count == 1
    details = quality.attrs["missing_data_details"]
    assert details.status.tolist() == ["EXPLAINED", "UNEXPLAINED"]
    assert details.iloc[0].reason == "market_suspension"


def test_tiingo_normalizer_defers_missing_without_filling():
    rows = [
        dict(date=d, close=c, adjClose=100, divCash=0, splitFactor=1)
        for d, c in [("2020-01-01", 100), ("2020-01-02", None), ("2020-01-03", 101)]
    ]
    frame = normalize(rows, policy="ignore", asset_id="US:VOO")
    assert pd.isna(frame.iloc[1].raw_close)
    with pytest.raises(DataQualityError):
        normalize(rows, policy="error", asset_id="US:VOO")


def test_clean_run_emits_empty_detail_schema(tmp_path, assets):
    clean = {"TW:0050": assets["A"], "TW:0056": assets["B"]}
    out = run(config(tmp_path, "warn"), clean)
    details = pd.read_csv(out["run_path"] / "results/missing_data_details.csv")
    assert details.empty
    assert list(details.columns) == [
        "asset_id",
        "date",
        "raw_missing",
        "adjusted_missing",
        "reason",
        "status",
    ]
    assert out["summary_metrics"].daily_metrics_reliable.all()
