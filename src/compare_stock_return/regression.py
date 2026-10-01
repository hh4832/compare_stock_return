"""OLS with Newey-West covariance; undefined constant regressors return NaN."""

import numpy as np
import statsmodels.api as sm


def fit(excess_asset, excess_benchmark) -> dict:
    if len(excess_asset) < 3 or excess_benchmark.std() == 0:
        return dict(beta=np.nan, alpha=np.nan, R_squared=np.nan, alpha_pvalue=np.nan)
    model = sm.OLS(
        excess_asset.to_numpy(), sm.add_constant(excess_benchmark.to_numpy())
    ).fit(cov_type="HAC", cov_kwds={"maxlags": min(5, len(excess_asset) - 1)})
    return dict(
        beta=float(model.params[1]),
        alpha=float(model.params[0] * 252),
        R_squared=float(model.rsquared),
        alpha_pvalue=float(model.pvalues[0]),
    )
