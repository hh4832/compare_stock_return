"""Adjusted-price returns already include provider corporate-action adjustment."""

import pandas as pd


def daily_returns(prices: pd.Series) -> pd.Series:
    return prices.pct_change(fill_method=None)


def return_columns(frame: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "price_return": daily_returns(frame.raw_close),
            "total_return": daily_returns(frame.adjusted_close),
        }
    )


def selected_price(frame: pd.DataFrame, return_type: str) -> pd.Series:
    return frame["adjusted_close" if return_type == "total_return" else "raw_close"]


def equity(prices: pd.Series) -> pd.Series:
    return 100 * prices / prices.iloc[0]
