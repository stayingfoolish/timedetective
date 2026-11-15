"""Did a relationship that used to hold between two series break down?"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.regression.rolling import RollingOLS
from statsmodels.stats.diagnostic import breaks_cusumolsresid

from timedetective.skills.registry import register
from timedetective.skills.relationship.align import guard_pair
from timedetective.skills.result import SkillResult, refuse


@register("rolling_regression")
def rolling_regression(x: pd.Series, y: pd.Series, window: int) -> SkillResult:
    """Slope of y on x within a moving window; returns the slope series (NaN until the window fills).

    Assumes a linear relationship inside each window; two aligned, regular, gap-free series.
    """
    name = "rolling_regression"
    if window < 10:
        return refuse(name, f"window must be at least 10, got {window}", "pass a longer window")
    if (r := guard_pair(name, x, y, 2 * window)) is not None:
        return r
    fit = RollingOLS(y.to_numpy(dtype=float), sm.add_constant(x.to_numpy(dtype=float)), window=window).fit()
    slope = pd.Series(fit.params[:, 1], index=x.index, name="rolling_slope")
    valid = slope.dropna()
    return SkillResult(
        name,
        {"window": window, "slope_min": float(valid.min()), "slope_max": float(valid.max()), "slope_range": float(np.ptp(valid.to_numpy()))},
        series=slope,
    )


@register("decoupling_test")
def decoupling_test(x: pd.Series, y: pd.Series, alpha: float = 0.05, min_segment: int = 10) -> SkillResult:
    """CUSUM test on the residuals of y regressed on x: a rejection means y stopped
    tracking x the way it did over the whole record.

    Assumes a linear relationship and little serial correlation in the residuals;
    two aligned, regular, gap-free series. `break_position` is where the
    cumulative residual peaks; `residual_shift` is the mean residual after minus
    before. This shows that the relationship changed, not why.
    """
    name = "decoupling_test"
    if (r := guard_pair(name, x, y, 2 * min_segment + 5)) is not None:
        return r
    a, b = x.to_numpy(dtype=float), y.to_numpy(dtype=float)
    fit = sm.OLS(b, sm.add_constant(a)).fit()
    stat, p, _ = breaks_cusumolsresid(fit.resid, ddof=2)
    interior = np.abs(np.cumsum(fit.resid))[min_segment - 1 : len(a) - min_segment]
    k = int(np.argmax(interior)) + min_segment
    return SkillResult(
        name,
        {
            "decoupled": bool(p < alpha),
            "p_value": float(p),
            "statistic": float(stat),
            "break_position": k,
            "break_time": x.index[k],
            "slope_full": float(fit.params[1]),
            "residual_shift": float(fit.resid[k:].mean() - fit.resid[:k].mean()),
            "alpha": alpha,
        },
        series=pd.Series(fit.resid, index=x.index, name="residual"),
    )
