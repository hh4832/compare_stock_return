"""Shared Colab/CLI engine, with injectable providers for offline verification."""

import logging
import time
import uuid
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import pandas as pd
import yaml

from . import data_loader
from .alignment import align, usable
from .benchmark import relative
from .drawdown import episodes
from .fees import fee_table, synthetic_fee_adjusted
from .holdings import analyze
from .metrics import calendar_returns, summary
from .plotting import export_charts
from .progress import Progress
from .reporting import checksums, environment, json_write, promote_latest
from .returns import return_columns, selected_price
from .rolling import rolling_metrics
from .symbol_resolver import resolve
from .validation import DataQualityError, validate_assets


def run(config, assets: dict | None = None, asset_metadata: dict | None = None) -> dict:
    config.validate()
    root = Path(config.drive_output_root)
    if not root.is_dir():
        raise FileNotFoundError(
            f"Output root does not exist: {root}. Create this exact folder explicitly."
        )
    started = time.monotonic()
    run_path = (
        root
        / "runs"
        / (
            datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            + "_"
            + uuid.uuid4().hex[:8]
        )
    )
    for folder in ["config", "data", "results", "charts", "logs", "metadata"]:
        (run_path / folder).mkdir(parents=True, exist_ok=False)
    logger = logging.getLogger(f"compare.{run_path.name}")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(run_path / "logs/run.log")
    logger.addHandler(handler)
    progress = Progress(config.progress)
    meta = dict(
        status="RUNNING",
        timestamp=datetime.now(timezone.utc).isoformat(),
        config=config.to_dict(),
        symbols=config.symbols,
    )
    try:
        progress.enter(1, "Environment")
        env = environment()
        meta.update(env)
        (run_path / "config/run_config.yaml").write_text(
            yaml.safe_dump(config.to_dict(), sort_keys=False)
        )
        json_write(run_path / "metadata/package_versions.json", env["packages"])
        progress.enter(2, "Authentication")
        if assets is None:
            logger.info("FinLab credentials resolved by loader; never serialized")
        progress.enter(3, "Loading data / resolving symbols")
        if assets is None:
            assets, asset_metadata, provenance = data_loader.load(
                config, root / "cache"
            )
        else:
            provenance = {"provider": "injected/custom fixture"}
        if set(assets) != set(config.symbols):
            raise ValueError("Provider assets must exactly match configured symbols")
        resolve(config.symbols, assets, asset_metadata).to_csv(
            run_path / "results/assets.csv", index=False
        )
        meta["provenance"] = provenance
        progress.enter(4, "Validating data")
        quality = validate_assets(assets, config.non_trading_dates)
        quality.to_csv(run_path / "results/data_quality_report.csv", index=False)
        meta["individual_periods"] = quality.astype(str).to_dict("records")
        progress.enter(5, "Aligning date ranges")
        common, window = align(assets)
        meta["common_comparison_range"] = window
        chosen = common
        if config.date_mode == "custom":
            chosen, selected_window = align(
                assets, config.custom_start_date, config.custom_end_date, config.strict
            )
        elif config.date_mode == "full_history":
            chosen = {s: usable(f) for s, f in assets.items()}
            selected_window = {
                "warning": "NOT DIRECTLY COMPARABLE DUE TO DIFFERENT DATE RANGES"
            }
        else:
            selected_window = window
        meta["selected_range"] = selected_window
        for row in quality.itertuples():
            print(
                f"{row.ticker} data: {row.first_valid_date.date()} → {row.last_valid_date.date()}"
            )
        print(
            f"COMMON WINDOW: {window['start_date']} → {window['end_date']} ({window['observations']} prices)"
        )
        if window["observations"] < 60:
            print("WARNING: common sample <60 trading days")
        progress.enter(6, "Calculating returns")
        prices = {s: selected_price(f, config.return_type) for s, f in chosen.items()}
        pd.concat(chosen, names=["ticker", "date"]).to_parquet(
            run_path / "data/aligned_prices.parquet"
        )
        pd.concat(
            {s: return_columns(f) for s, f in chosen.items()}, names=["ticker", "date"]
        ).to_parquet(run_path / "data/returns.parquet")
        pd.concat(assets, names=["ticker", "date"]).to_parquet(
            run_path / "data/source_prices.parquet"
        )
        progress.enter(7, "Rolling metrics / drawdowns / risk analytics")

        def table(frames):
            return pd.DataFrame(
                [
                    dict(
                        ticker=s,
                        **summary(
                            selected_price(f, config.return_type), config.risk_free_rate
                        ),
                    )
                    for s, f in frames.items()
                ]
            )

        headline = table(chosen)
        intersection = table(common)
        full = table({s: usable(f) for s, f in assets.items()})
        full["comparability_warning"] = (
            "NOT DIRECTLY COMPARABLE DUE TO DIFFERENT DATE RANGES"
        )
        for name, frame in [
            ("summary_metrics", headline),
            ("intersection_metrics", intersection),
            ("full_history_metrics", full),
        ]:
            frame.to_csv(run_path / f"results/{name}.csv", index=False)
        rolls = {
            s: rolling_metrics(p, config.risk_free_rate) for s, p in prices.items()
        }
        pd.concat(rolls, names=["ticker", "date"]).to_csv(
            run_path / "results/rolling_metrics.csv"
        )
        pd.concat(
            {s: episodes(p) for s, p in prices.items()}, names=["ticker", "episode"]
        ).to_csv(run_path / "results/drawdowns.csv")
        for freq, name in [("Y", "annual"), ("M", "monthly")]:
            records = pd.concat(
                [calendar_returns(p, freq).assign(ticker=s) for s, p in prices.items()],
                ignore_index=True,
            )
            records.to_csv(run_path / f"results/{name}_returns.csv", index=False)
            records.pivot(
                index="period", columns="ticker", values="return_value"
            ).to_csv(run_path / f"results/{name}_returns_wide.csv")
        progress.enter(8, "Benchmark / pairwise analytics")
        pairwise = []
        benchmarks = []
        monthly_excess = []
        for a, b in combinations(config.symbols, 2):
            pair, info = align({a: assets[a], b: assets[b]})
            result = relative(
                selected_price(pair[a], config.return_type),
                selected_price(pair[b], config.return_type),
                config.risk_free_rate,
            )
            result.pop("monthly_excess_returns")
            result.update(
                asset_a=a,
                asset_b=b,
                calendar_exclusions=str(info["excluded_calendar_dates"]),
            )
            pairwise.append(result)
        for s in config.symbols:
            if s == config.benchmark:
                continue
            pair, info = align(
                {s: assets[s], config.benchmark: assets[config.benchmark]}
            )
            result = relative(
                selected_price(pair[s], config.return_type),
                selected_price(pair[config.benchmark], config.return_type),
                config.risk_free_rate,
            )
            monthly = result.pop("monthly_excess_returns").assign(
                ticker=s, benchmark=config.benchmark
            )
            monthly_excess.append(monthly)
            result.update(
                ticker=s,
                benchmark=config.benchmark,
                calendar_exclusions=str(info["excluded_calendar_dates"]),
            )
            benchmarks.append(result)
        pair_columns = [
            "asset_a",
            "asset_b",
            "start_date",
            "end_date",
            "observations",
            "asset_a_cagr",
            "asset_b_cagr",
            "cagr_difference",
            "asset_a_mdd",
            "asset_b_mdd",
            "correlation",
            "beta",
            "alpha",
            "tracking_error",
            "information_ratio",
        ]
        pd.DataFrame(pairwise, columns=None if pairwise else pair_columns).to_csv(
            run_path / "results/pairwise_metrics.csv", index=False
        )
        pd.DataFrame(
            benchmarks,
            columns=None
            if benchmarks
            else ["ticker", "benchmark", "start_date", "end_date", "observations"],
        ).to_csv(run_path / "results/benchmark_metrics.csv", index=False)
        pd.concat(monthly_excess, ignore_index=True).to_csv(
            run_path / "results/monthly_excess_returns.csv", index=False
        ) if monthly_excess else pd.DataFrame(
            columns=["ticker", "benchmark", "period", "excess_return"]
        ).to_csv(run_path / "results/monthly_excess_returns.csv", index=False)
        fee_table(config.symbols, config.fees).to_csv(
            run_path / "results/fees.csv", index=False
        )
        scenarios = []
        for s, spec in config.fees.items():
            if spec.get("apply_synthetic", False):
                scenario = synthetic_fee_adjusted(
                    prices[s],
                    spec["annual_expense_ratio"],
                    spec.get("already_included", False),
                )
                scenarios.append(
                    dict(
                        ticker=s,
                        accounting="synthetic additional fee scenario",
                        **summary(scenario, config.risk_free_rate),
                    )
                )
        pd.DataFrame(scenarios).to_csv(
            run_path / "results/synthetic_fee_metrics.csv", index=False
        )
        meta["holdings_status"] = "skipped: no reliable dated holdings supplied"
        if config.holdings_files:
            try:
                concentration, overlap = analyze(config.holdings_files)
                concentration.to_csv(
                    run_path / "results/holdings_concentration.csv", index=False
                )
                overlap.to_csv(run_path / "results/holdings_overlap.csv", index=False)
                meta["holdings_status"] = "user-supplied dated snapshots"
            except (ValueError, OSError, KeyError) as exc:
                logger.warning("Optional holdings skipped: %s", exc)
                meta["holdings_status"] = f"skipped: {exc}"
        progress.enter(9, "Generating charts")
        export_charts(prices, rolls, config, run_path / "charts")
        progress.enter(10, "Exporting results")
        meta.update(
            status="SUCCESS",
            runtime_seconds=time.monotonic() - started,
            limitations=[
                "Provider-adjusted return proxy; corporate actions not independently reconstructed",
                "Raw price return includes split jumps",
                "No investor tax, trading cost or reinvestment friction",
                "No linkage-fund NAV supplied unless explicitly configured",
            ],
        )
        json_write(run_path / "metadata/run_metadata.json", meta)
        logger.info("SUCCESS %s", run_path)
        handler.flush()
        json_write(run_path / "metadata/checksums.json", checksums(run_path))
        promote_latest(run_path, root)
        progress.close(True)
        print(
            f"Assets: {', '.join(config.symbols)}\nReturn type: {config.return_type}\nOutput: {run_path}\nRuntime: {meta['runtime_seconds']:.1f}s\nStatus: SUCCESS"
        )
        return dict(
            run_path=run_path,
            intersection_metrics=intersection,
            summary_metrics=headline,
            metadata=meta,
        )
    except Exception as exc:
        if isinstance(exc, DataQualityError):
            exc.report.to_csv(run_path / "results/data_quality_report.csv", index=False)
        meta.update(
            status="FAILED",
            failed_stage=progress.stage,
            error_type=type(exc).__name__,
            runtime_seconds=time.monotonic() - started,
        )
        # Do not serialize provider exception payloads that could contain credentials.
        json_write(run_path / "metadata/run_metadata.json", meta)
        logger.error("FAILED at stage %s (%s)", progress.stage, type(exc).__name__)
        progress.close(False)
        print(f"FAILED at stage: {progress.stage}; retained run: {run_path}")
        raise
    finally:
        logger.removeHandler(handler)
        handler.close()
