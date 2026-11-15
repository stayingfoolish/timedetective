"""Least-squares linear trend, with ordinary and autocorrelation-robust standard errors."""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from timedetective.skills.checks import guard, time_axis
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult


def _fit(name: str, x: pd.Series, alpha: float, hac_lags: int | None) -> SkillResult:
    t, unit = time_axis(x)
    model = sm.OLS(x.to_numpy(dtype=float), sm.add_constant(t))
    fit = model.fit() if hac_lags is None else model.fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})
    lo, hi = fit.conf_int(alpha)[1]
    values = {
        "slope": float(fit.params[1]),
        "slope_unit": f"per {unit}",
        "intercept": float(fit.params[0]),
        "ci_low": float(lo),
        "ci_high": float(hi),
        "p_value": float(fit.pvalues[1]),
        "alpha": alpha,
        "r_squared": float(fit.rsquared),
        "n": len(x),
    }
    if hac_lags is not None:
        values["hac_lags"] = hac_lags
    resid = pd.Series(fit.resid, index=x.index, name="residual")
    return SkillResult(name, values, series=resid)


@register("ols_trend")
def ols_trend(x: pd.Series, alpha: float = 0.05) -> SkillResult:
    """Slope, confidence interval and p-value from ordinary least squares on time.

    Assumes a linear trend with uncorrelated, constant-variance residuals; with
    autocorrelated residuals the interval is too narrow. Returns residuals as `series`.
    """
    name = "ols_trend"
    if (r := guard(name, x, 10)) is not None:
        return r
    return _fit(name, x, alpha, None)


@register("ols_trend_hac")
def ols_trend_hac(x: pd.Series, alpha: float = 0.05, maxlags: int | None = None) -> SkillResult:
    """OLS slope with Newey-West (HAC) standard errors, valid under autocorrelated residuals.

    Assumes a linear trend. Default lag truncation is floor(4 * (n/100)^(2/9)).
    Returns residuals as `series`.
    """
    name = "ols_trend_hac"
    if (r := guard(name, x, 20)) is not None:
        return r
    lags = maxlags if maxlags is not None else int(np.floor(4 * (len(x) / 100) ** (2 / 9)))
    return _fit(name, x, alpha, lags)
