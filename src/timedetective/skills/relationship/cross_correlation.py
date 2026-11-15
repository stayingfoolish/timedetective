"""Do two series move together, and which one leads?"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from timedetective.skills.registry import register
from timedetective.skills.relationship.align import guard_pair
from timedetective.skills.result import SkillResult, refuse


@register("lagged_cross_correlation")
def lagged_cross_correlation(x: pd.Series, y: pd.Series, max_lag: int = 12) -> SkillResult:
    """Correlation of x[t-k] with y[t] for k in [-max_lag, max_lag]; reports the strongest.

    A positive `best_lag` means x leads y by that many steps. Assumes both series
    are regular, aligned, and already detrended and deseasonalized: shared trend
    or season produces high correlation at every lag. The significance bound
    1.96/sqrt(n-|k|) assumes at least one series is white noise, and the best of
    many lags is not adjusted for the search.
    """
    name = "lagged_cross_correlation"
    if max_lag < 0:
        return refuse(name, f"max_lag must be non-negative, got {max_lag}", "pass a non-negative max_lag")
    if (r := guard_pair(name, x, y, max(20, 3 * max_lag))) is not None:
        return r
    a, b = x.to_numpy(dtype=float), y.to_numpy(dtype=float)
    n = len(a)
    lags = list(range(-max_lag, max_lag + 1))
    corr = [
        float(np.corrcoef(a[: n - k], b[k:])[0, 1]) if k >= 0 else float(np.corrcoef(a[-k:], b[: n + k])[0, 1])
        for k in lags
    ]
    i = int(np.argmax(np.abs(corr)))
    bound = 1.96 / np.sqrt(n - abs(lags[i]))
    return SkillResult(name, {
        "best_lag": lags[i],
        "correlation": corr[i],
        "correlation_at_zero": corr[max_lag],
        "bound": float(bound),
        "correlated": bool(abs(corr[i]) > bound),
        "lags": lags,
        "correlations": corr,
    })


@register("partial_correlation")
def partial_correlation(x: pd.Series, y: pd.Series, z: pd.Series, alpha: float = 0.05) -> SkillResult:
    """Correlation of x and y after regressing a shared driver z out of both.

    Assumes linear relationships and independent observations; three aligned,
    regular, gap-free series.
    """
    name = "partial_correlation"
    for other in (y, z):
        if (r := guard_pair(name, x, other, 20)) is not None:
            return r
    design = sm.add_constant(z.to_numpy(dtype=float))
    rx = sm.OLS(x.to_numpy(dtype=float), design).fit().resid
    ry = sm.OLS(y.to_numpy(dtype=float), design).fit().resid
    rho = float(np.corrcoef(rx, ry)[0, 1])
    dof = len(x) - 3
    t = rho * np.sqrt(dof / max(1e-12, 1 - rho**2))
    p = float(2 * stats.t.sf(abs(t), dof))
    return SkillResult(name, {
        "partial_correlation": rho,
        "raw_correlation": float(np.corrcoef(x.to_numpy(dtype=float), y.to_numpy(dtype=float))[0, 1]),
        "p_value": p,
        "correlated": bool(p < alpha),
        "alpha": alpha,
    })
