import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def assets():
    dates = pd.bdate_range("2020-01-01", periods=100)
    a = 100 * np.cumprod(1 + np.sin(np.arange(100)) * 0.015 + 0.001)
    b = 80 * np.cumprod(1 + np.cos(np.arange(100)) * 0.01 + 0.001)
    return {
        "A": pd.DataFrame({"raw_close": a, "adjusted_close": a}, index=dates),
        "B": pd.DataFrame(
            {"raw_close": b[20:], "adjusted_close": b[20:]}, index=dates[20:]
        ),
    }
