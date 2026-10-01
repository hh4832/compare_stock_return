"""Matching HTML and PNG plots, with explicit range and return accounting."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .drawdown import underwater
from .metrics import calendar_returns
from .returns import equity


def export_charts(prices: dict, rolling: dict, config, destination: Path) -> None:
    display = (
        config.display_symbols if config.display_symbols is not None else list(prices)
    )
    displayed = {s: p for s, p in prices.items() if s in display}
    if not displayed:
        return
    specs = {
        "normalized_equity_curve": (
            {s: equity(p) for s, p in displayed.items()},
            "NAV (start=100)",
        ),
        "underwater": ({s: underwater(p) for s, p in displayed.items()}, "Drawdown"),
        "rolling_12m_return": ({s: rolling[s].return_12m for s in displayed}, "Return"),
        "rolling_36m_return": (
            {s: rolling[s].return_36m for s in displayed},
            "Annualized return",
        ),
        "rolling_36m_volatility": (
            {s: rolling[s].volatility_36m for s in displayed},
            "Annualized volatility",
        ),
        "rolling_sharpe": ({s: rolling[s].Sharpe_12m for s in displayed}, "Sharpe"),
    }
    specs["rolling_volatility"] = (
        {s: rolling[s].volatility_12m for s in displayed},
        "Annualized volatility",
    )
    bench = rolling[config.benchmark].return_12m
    specs["rolling_excess_return"] = (
        {
            s: rolling[s].return_12m - bench
            for s in displayed
            if s != config.benchmark
            and (":" not in s or s.split(":")[0] == config.benchmark.split(":")[0])
        },
        "12M return difference",
    )
    monthly = pd.concat(
        {
            s: calendar_returns(p, "M").set_index("period").return_value
            for s, p in displayed.items()
        },
        axis=1,
    )
    heat = go.Figure(
        go.Heatmap(
            z=monthly.T.to_numpy(),
            x=monthly.index,
            y=monthly.columns,
            colorscale="RdBu",
            zmid=0,
        )
    )
    heat.update_layout(
        title="Monthly returns (boundary months may be partial) | LOCAL CURRENCY RETURNS — FX EXCLUDED"
    )
    heat.write_html(destination / "monthly_return_heatmap.html", include_plotlyjs=True)
    static_heat, heat_ax = plt.subplots(figsize=(11, 5))
    heat_ax.imshow(
        np.ma.masked_invalid(monthly.T.to_numpy()), aspect="auto", cmap="RdBu"
    )
    heat_ax.set_yticks(range(len(monthly.columns)), labels=monthly.columns)
    step = max(1, len(monthly) // 10)
    heat_ax.set_xticks(
        range(0, len(monthly), step), labels=monthly.index[::step], rotation=45
    )
    heat_ax.set_title("Monthly returns; boundary months may be partial; FX excluded")
    static_heat.tight_layout()
    static_heat.savefig(destination / "monthly_return_heatmap.png", dpi=150)
    plt.close(static_heat)
    start = min(p.index[0] for p in displayed.values()).date()
    end = max(p.index[-1] for p in displayed.values()).date()
    for name, (series, label) in specs.items():
        title = f"LOCAL CURRENCY RETURNS — FX EXCLUDED | {name.replace('_', ' ')} | {start} → {end} | {config.return_type}"
        if getattr(config, "data_quality_warning", False):
            title += " | DAILY_METRICS_HAVE_MISSING_SESSION_WARNING"
        if name == "rolling_excess_return":
            title += f" | benchmark {config.benchmark}"
        if config.date_mode == "full_history":
            title += " | NOT DIRECTLY COMPARABLE DUE TO DIFFERENT DATE RANGES"
        fig = go.Figure()
        static, ax = plt.subplots(figsize=(11, 5))
        for symbol, values in series.items():
            fig.add_trace(
                go.Scatter(x=values.index, y=values, name=symbol, mode="lines")
            )
            ax.plot(values.index, values, label=symbol)
        source = "Source: FinLab / Tiingo / confirmed custom NAV; LOCAL CURRENCY RETURNS — FX EXCLUDED; no filling"
        fig.update_layout(
            title=title,
            xaxis_title="Date",
            yaxis_title=label,
            template="plotly_white",
            annotations=[
                dict(
                    text=source,
                    x=0,
                    y=-0.25,
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                )
            ],
        )
        fig.write_html(destination / f"{name}.html", include_plotlyjs=True)
        ax.set(title=title, xlabel="Date", ylabel=label)
        if series:
            ax.legend()
        static.text(0.01, 0.01, source, fontsize=8)
        static.tight_layout(rect=(0, 0.04, 1, 1))
        static.savefig(destination / f"{name}.png", dpi=150)
        plt.close(static)


def export_portfolio_charts(navs, destination):
    for name, transform, label in [
        ("model_portfolio_equity_curve", equity, "NAV (start=100)"),
        ("model_portfolio_drawdown", underwater, "Monthly drawdown"),
    ]:
        fig = go.Figure()
        static, ax = plt.subplots(figsize=(11, 5))
        for portfolio, nav in navs.items():
            values = transform(nav)
            fig.add_trace(go.Scatter(x=values.index, y=values, name=portfolio))
            ax.plot(values.index, values, label=portfolio)
        title = name + " | LOCAL CURRENCY RETURNS — FX EXCLUDED | monthly rebalancing"
        fig.update_layout(title=title, yaxis_title=label, template="plotly_white")
        fig.write_html(destination / (name + ".html"), include_plotlyjs=True)
        ax.set(title=title, ylabel=label)
        if navs:
            ax.legend()
        static.tight_layout()
        static.savefig(destination / (name + ".png"), dpi=150)
        plt.close(static)
