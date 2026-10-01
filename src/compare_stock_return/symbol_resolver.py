"""Single mapping entry point; unknown labels are explicit, never invented."""

import pandas as pd


def resolve(
    symbols: list[str], available, metadata: dict | None = None
) -> pd.DataFrame:
    rows = []
    for s in symbols:
        if s not in available:
            raise ValueError(f"Ticker {s} unavailable from provider")
        m = (metadata or {}).get(s, {})
        rows.append(
            dict(
                ticker=s,
                asset_name=m.get("name", "unknown (provider metadata unavailable)"),
                asset_type=m.get("type", "unknown"),
            )
        )
    return pd.DataFrame(rows)
