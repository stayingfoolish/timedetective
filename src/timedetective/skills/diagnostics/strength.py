"""How dominant the trend and the season are, from an STL decomposition."""

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL

from timedetective.skills.checks import guard
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("component_strength")
def component_strength(x: pd.Series, period: int, robust: bool = True) -> SkillResult:
    """Trend strength and seasonal strength in [0, 1]: 1 - Var(R)/Var(component + R).

    Assumes a regular, gap-free series with a known period and two or more full cycles.
    """
    name = "component_strength"
    if period < 2:
        return refuse(name, f"period must be at least 2, got {period}", "pass the seasonal period")
    if (r := guard(name, x, 2 * period + 1)) is not None:
        return r
    fit = STL(x.to_numpy(dtype=float), period=period, robust=robust).fit()
    var_r = np.var(fit.resid)
    return SkillResult(name, {
        "trend_strength": float(max(0.0, 1 - var_r / np.var(fit.trend + fit.resid))),
        "seasonal_strength": float(max(0.0, 1 - var_r / np.var(fit.seasonal + fit.resid))),
        "period": period,
    })
