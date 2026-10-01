"""Shared Colab/CLI engine, with injectable providers for offline verification."""

import logging
import time
import uuid
from copy import copy
from dataclasses import asdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import pandas as pd
import yaml

from . import data_loader
from .alignment import align, usable
from .asset_id import parse_asset_id
from .benchmark import relative
from .cross_market import monthly_metrics
from .drawdown import episodes
from .fees import fee_table, synthetic_fee_adjusted
from .holdings import analyze
from .metrics import calendar_returns, summary
from .model_portfolio import simulate
from .plotting import export_charts, export_portfolio_charts
from .progress import Progress
from .reporting import checksums, environment, json_write, promote_latest
from .returns import return_columns, selected_price
from .rolling import rolling_metrics
from .symbol_resolver import resolve
from .validation import (
    DAILY_WARNING,
    DataQualityError,
    gap_annotations,
    validate_assets,
)


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
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(handler)
    progress = Progress(config.progress)
    meta = dict(
        status="RUNNING",
        timestamp=datetime.now(timezone.utc).isoformat(),
        config=config.to_dict(),
        symbols=config.symbols,
        missing_data_policy=config.missing_data_policy,
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
            logger.info("Provider credentials resolved by loader; never serialized")
        progress.enter(3, "Loading data / resolving symbols")
        if assets is None:
            assets, asset_metadata, provenance = data_loader.load(
                config, root / "cache"
            )
        else:
            provenance = {"provider": "injected/custom fixture"}
        if set(assets) != set(config.symbols):
            raise ValueError("Provider assets must exactly match configured symbols")
        identities = (
            {a: asdict(parse_asset_id(a)) for a in config.symbols}
            if config.assets is not None
            else {}
        )
        resolved = resolve(config.symbols, assets, asset_metadata)
        if identities:
            for col in ["asset_id", "symbol", "market", "currency", "provider"]:
                resolved[col] = resolved.ticker.map(lambda a: identities[a][col])
        resolved.to_csv(run_path / "results/assets.csv", index=False)
        meta["provenance"] = provenance
        meta.update(
            assets=list(identities.values()),
            fx_mode=config.fx_mode,
            return_accounting="Cross-market returns are measured in each asset's local currency. FX effects are intentionally excluded.",
            portfolio_assumptions=dict(
                rebalancing="monthly",
                accounting="local-currency model returns",
                fx="excluded",
            ),
            calendar_limitation="Tiingo absent session rows are not independently verified; other markets never define missing sessions",
        )
        meta["corporate_action_availability"] = {
            a: "Tiingo EOD divCash/splitFactor"
            if {"divCash", "splitFactor"} <= set(frame)
            else "provider event data unavailable"
            for a, frame in assets.items()
        }
        actions = []
        for a, frame in assets.items():
            if {"divCash", "splitFactor"} <= set(frame):
                actions.append(
                    frame[["divCash", "splitFactor"]].assign(
                        asset_id=a, provider="tiingo"
                    )
                )
        (
            pd.concat(actions)
            if actions
            else pd.DataFrame(
                columns=["divCash", "splitFactor", "asset_id", "provider"]
            )
        ).to_parquet(run_path / "data/corporate_actions.parquet")
        progress.enter(4, "Validating data")
        quality = validate_assets(
            assets, config.non_trading_dates, config.missing_data_policy, logger
        )
        quality.to_csv(run_path / "results/data_quality_report.csv", index=False)
        details = quality.attrs["missing_data_details"]
        details.to_csv(run_path / "results/missing_data_details.csv", index=False)
        meta["individual_periods"] = quality.astype(str).to_dict("records")
        meta["missing_data_by_asset"] = quality[
            [
                "asset_id",
                "missing_count",
                "explained_missing_count",
                "unexplained_missing_count",
                "unexplained_missing_dates",
                "daily_metrics_reliable",
                "validation_status",
            ]
        ].to_dict("records")
        quality_by_asset = quality.set_index("asset_id").to_dict("index")

        def asset_warning(asset_id):
            q = quality_by_asset[asset_id]
            return dict(
                daily_metrics_reliable=q["daily_metrics_reliable"],
                daily_metrics_status="OK"
                if q["daily_metrics_reliable"]
                else DAILY_WARNING,
                validation_status=q["validation_status"],
                unexplained_missing_count=q["unexplained_missing_count"],
                missing_count=q["missing_count"],
                return_observation_policy="returns connect available observations; intervals spanning excluded missing sessions are not ordinary daily observations",
            )

        def pair_warning(a, b, pair, daily=True):
            annotation = dict(
                daily_metrics_reliable=bool(
                    quality_by_asset[a]["daily_metrics_reliable"]
                    and quality_by_asset[b]["daily_metrics_reliable"]
                )
            )
            annotation["daily_metrics_status"] = (
                "OK" if annotation["daily_metrics_reliable"] else DAILY_WARNING
            )
            # relative() inner-joins usable prices; count dropped source rows, including missing sessions.
            joined = pair[a].index.intersection(pair[b].index)
            for label, asset in [("a", a), ("b", b)]:
                start, end = (
                    max(pair[a].index[0], pair[b].index[0]),
                    min(pair[a].index[-1], pair[b].index[-1]),
                )
                own = details.loc[
                    (details.asset_id == asset)
                    & (details.date >= start)
                    & (details.date <= end)
                ]
                source_dates = assets[asset].loc[start:end].index
                annotation[f"excluded_sessions_{label}"] = len(
                    source_dates.difference(joined if daily else pair[asset].index)
                )
                annotation[f"excluded_missing_sessions_{label}"] = len(own)
                annotation[f"unexplained_missing_sessions_{label}"] = int(
                    (own.status == "UNEXPLAINED").sum()
                )
                annotation[f"missing_dates_{label}"] = ";".join(
                    str(d.date()) for d in own.date
                )
            return annotation

        for row in quality.itertuples():
            for col in ["first_valid_date", "last_valid_date"]:
                resolved.loc[resolved.ticker == row.ticker, col] = str(
                    getattr(row, col).date()
                )
        resolved.to_csv(run_path / "results/assets.csv", index=False)
        progress.enter(5, "Aligning date ranges")
        common, window = align(assets, calendar=config.assets is not None)
        meta["common_comparison_range"] = window
        chosen = common
        if config.date_mode == "custom":
            chosen, selected_window = align(
                assets,
                config.custom_start_date,
                config.custom_end_date,
                config.strict,
                calendar=config.assets is not None,
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
        audited_returns = {}
        for asset, frame in chosen.items():
            audited_returns[asset] = (
                return_columns(frame)
                .join(gap_annotations(frame.index, details, asset))
                .assign(**asset_warning(asset))
            )
        pd.concat(audited_returns, names=["ticker", "date"]).to_parquet(
            run_path / "data/returns.parquet"
        )
        pd.concat(assets, names=["ticker", "date"]).to_parquet(
            run_path / "data/source_prices.parquet"
        )
        progress.enter(7, "Rolling metrics / drawdowns / risk analytics")

        def table(frames, calendar_window=None):
            return pd.DataFrame(
                [
                    dict(
                        ticker=s,
                        common_calendar_start=(calendar_window or {}).get("start_date"),
                        common_calendar_end=(calendar_window or {}).get("end_date"),
                        **identities.get(s, {}),
                        **asset_warning(s),
                        **summary(
                            selected_price(f, config.return_type), config.risk_free_rate
                        ),
                    )
                    for s, f in frames.items()
                ]
            )

        headline = table(chosen, selected_window)
        intersection = table(common, window)
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
            s: rolling_metrics(p, config.risk_free_rate)
            .join(gap_annotations(p.index, details, s))
            .assign(**asset_warning(s))
            for s, p in prices.items()
        }
        pd.concat(rolls, names=["ticker", "date"]).to_csv(
            run_path / "results/rolling_metrics.csv"
        )
        pd.concat(
            {s: episodes(p) for s, p in prices.items()}, names=["ticker", "episode"]
        ).to_csv(run_path / "results/drawdowns.csv")
        for freq, name in [("Y", "annual"), ("M", "monthly")]:
            records = pd.concat(
                [
                    calendar_returns(p, freq).assign(ticker=s, **asset_warning(s))
                    for s, p in prices.items()
                ],
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
        cross_monthly = []
        for a, b in combinations(config.symbols, 2):
            pair, info = align(
                {a: assets[a], b: assets[b]}, calendar=config.assets is not None
            )
            cross = bool(
                identities and identities[a]["market"] != identities[b]["market"]
            )
            if cross:
                result = monthly_metrics(
                    selected_price(pair[a], config.return_type),
                    selected_price(pair[b], config.return_type),
                )
                result.update(
                    asset_a=a,
                    asset_b=b,
                    start_date=info["start_date"],
                    end_date=info["end_date"],
                    per_asset_observations=str(info["per_asset_observations"]),
                )
                result.update(pair_warning(a, b, pair, daily=False))
                cross_monthly.append(result)
                pairwise.append(result)
                continue
            result = relative(
                selected_price(pair[a], config.return_type),
                selected_price(pair[b], config.return_type),
                config.risk_free_rate,
            )
            result.update(pair_warning(a, b, pair))
            result.pop("monthly_excess_returns")
            result.update(
                asset_a=a,
                asset_b=b,
                comparison_type="same_market_daily",
                calendar_exclusions=str(info["excluded_calendar_dates"]),
            )
            pairwise.append(result)
        for s in config.symbols:
            if s == config.benchmark:
                continue
            pair, info = align(
                {s: assets[s], config.benchmark: assets[config.benchmark]},
                calendar=config.assets is not None,
            )
            if (
                identities
                and identities[s]["market"] != identities[config.benchmark]["market"]
            ):
                result = monthly_metrics(
                    selected_price(pair[s], config.return_type),
                    selected_price(pair[config.benchmark], config.return_type),
                )
                result.update(
                    ticker=s,
                    benchmark=config.benchmark,
                    start_date=info["start_date"],
                    end_date=info["end_date"],
                )
                result.update(pair_warning(s, config.benchmark, pair, daily=False))
                benchmarks.append(result)
                continue
            result = relative(
                selected_price(pair[s], config.return_type),
                selected_price(pair[config.benchmark], config.return_type),
                config.risk_free_rate,
            )
            result.update(pair_warning(s, config.benchmark, pair))
            monthly = result.pop("monthly_excess_returns").assign(
                daily_metrics_reliable=result["daily_metrics_reliable"],
                daily_metrics_status=result["daily_metrics_status"],
                ticker=s,
                benchmark=config.benchmark,
            )
            monthly_excess.append(monthly)
            result.update(
                ticker=s,
                benchmark=config.benchmark,
                comparison_type="same_market_daily",
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
        meta["comparison_classification"] = [
            {k: row[k] for k in ("asset_a", "asset_b", "comparison_type")}
            for row in pairwise
        ]
        pd.DataFrame(
            cross_monthly,
            columns=None
            if cross_monthly
            else [
                "asset_a",
                "asset_b",
                "comparison_type",
                "monthly_correlation",
                "monthly_covariance",
            ],
        ).to_csv(run_path / "results/cross_market_monthly_metrics.csv", index=False)
        portfolio_metrics, portfolio_months, portfolio_years, portfolio_navs = simulate(
            prices, config.portfolios, config.risk_free_rate
        )
        for frame in [portfolio_metrics, portfolio_months, portfolio_years]:
            if len(frame):
                frame["underlying_prices_have_missing_session_warning"] = (
                    frame.portfolio.map(
                        lambda name: any(
                            not quality_by_asset[a]["daily_metrics_reliable"]
                            for a in config.portfolios[name]
                        )
                    )
                )
        for name, frame in [
            ("model_portfolio_metrics", portfolio_metrics),
            ("model_portfolio_monthly_returns", portfolio_months),
            ("model_portfolio_annual_returns", portfolio_years),
        ]:
            frame.to_csv(run_path / f"results/{name}.csv", index=False)
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
                        **asset_warning(s),
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
        chart_config = copy(config)
        chart_config.data_quality_warning = bool(
            (quality.unexplained_missing_count > 0).any()
        )
        export_charts(prices, rolls, chart_config, run_path / "charts")
        export_portfolio_charts(portfolio_navs, run_path / "charts")
        progress.enter(10, "Exporting results")
        meta["data_quality_status"] = (
            "WARNING" if (quality.unexplained_missing_count > 0).any() else "PASS"
        )
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
            model_portfolio_metrics=portfolio_metrics,
            metadata=meta,
        )
    except Exception as exc:
        if isinstance(exc, DataQualityError):
            exc.report.to_csv(run_path / "results/data_quality_report.csv", index=False)
            exc.details.to_csv(
                run_path / "results/missing_data_details.csv", index=False
            )
            meta["missing_data_by_asset"] = exc.report.to_dict("records")
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
