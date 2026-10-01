"""Fee metadata never alters observed returns. Scenarios require explicit opt-in."""

import pandas as pd


def fee_table(symbols: list[str], fees: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            dict(
                ticker=s,
                **fees.get(s, {}),
                accounting="reference only; observed prices unchanged",
            )
            for s in symbols
        ]
    )


def synthetic_fee_adjusted(
    prices: pd.Series, annual_expense_ratio: float, already_included: bool = False
) -> pd.Series:
    if already_included:
        raise ValueError("Cannot double deduct an already included fee")
    if not 0 <= annual_expense_ratio < 1:
        raise ValueError("Invalid expense ratio")
    years = (prices.index - prices.index[0]).days / 365.25
    return prices * (1 - annual_expense_ratio) ** years
