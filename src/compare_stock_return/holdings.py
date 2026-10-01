"""Optional user-supplied dated holdings, never inferred from today's constituents."""

from itertools import combinations

import numpy as np
import pandas as pd


def analyze(files: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    weights, rows, overlaps = {}, [], []
    for symbol, path in files.items():
        frame = pd.read_csv(path, dtype={"ticker": str})
        if not {"ticker", "weight", "as_of_date", "source"} <= set(frame):
            raise ValueError(
                "Holdings require ticker, weight (fraction), as_of_date, source"
            )
        if (
            frame.ticker.duplicated().any()
            or frame.as_of_date.nunique() != 1
            or frame.source.isna().any()
        ):
            raise ValueError("Holdings must have unique tickers, one date and sources")
        w = frame.set_index("ticker").weight.astype(float).sort_values(ascending=False)
        if (
            (w < 0).any()
            or not np.isfinite(w).all()
            or not np.isclose(w.sum(), 1, atol=0.001)
        ):
            raise ValueError("Holdings weights must sum to one")
        weights[symbol] = (w, frame.as_of_date.iloc[0])
        hhi = float((w * w).sum())
        rows.append(
            dict(
                ticker=symbol,
                as_of_date=frame.as_of_date.iloc[0],
                source=";".join(frame.source.unique()),
                number_of_holdings=len(w),
                top_1=w.head(1).sum(),
                top_5=w.head(5).sum(),
                top_10=w.head(10).sum(),
                HHI=hhi,
                effective_number_of_holdings=1 / hhi,
            )
        )
    for a, b in combinations(weights, 2):
        wa, da = weights[a]
        wb, db = weights[b]
        common = wa.index.intersection(wb.index)
        overlaps.append(
            dict(
                asset_a=a,
                asset_b=b,
                as_of_date_a=da,
                as_of_date_b=db,
                comparable_dates=da == db,
                common_holdings_count=len(common),
                overlap_ratio=len(common) / len(wa.index.union(wb.index)),
                weighted_overlap=np.minimum(wa.loc[common], wb.loc[common]).sum(),
            )
        )
    return pd.DataFrame(rows), pd.DataFrame(overlaps)
