"""Matching HTML and PNG plots, with explicit range and return accounting."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import plotly.graph_objects as go

from .drawdown import underwater
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
        "rolling_sharpe": ({s: rolling[s].Sharpe_36m for s in displayed}, "Sharpe"),
    }
    bench = rolling[config.benchmark].return_12m
    specs["rolling_excess_return"] = (
        {s: rolling[s].return_12m - bench for s in displayed if s != config.benchmark},
        "12M return difference",
    )
    start = min(p.index[0] for p in displayed.values()).date()
    end = max(p.index[-1] for p in displayed.values()).date()
    for name, (series, label) in specs.items():
        title = f"{name.replace('_', ' ')} | {start} → {end} | {config.return_type}"
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
        source = "Source: FinLab adjusted/raw close or explicitly supplied custom NAV; no filling"
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
