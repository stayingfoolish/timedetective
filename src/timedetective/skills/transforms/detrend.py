"""Differencing, linear detrending and lag-1 prewhitening."""

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import acf

from timedetective.skills.checks import guard, time_axis
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("difference")
def difference(x: pd.Series, lag: int = 1) -> SkillResult:
    """x[t] - x[t-lag], dropping the first `lag` points. Assumes a regular, gap-free series."""
    name = "difference"
    if lag < 1:
        return refuse(name, f"lag must be at least 1, got {lag}", "pass a positive lag")
    if (r := guard(name, x, lag + 2)) is not None:
        return r
    return SkillResult(name, {"lag": lag, "differenced": True}, series=x.diff(lag).iloc[lag:])


@register("detrend_linear")
def detrend_linear(x: pd.Series) -> SkillResult:
    """Residuals from a least-squares straight line. Assumes the trend is linear."""
    name = "detrend_linear"
    if (r := guard(name, x, 3)) is not None:
        return r
    t, unit = time_axis(x)
    slope, intercept = np.polyfit(t, x.to_numpy(dtype=float), 1)
    out = x - (intercept + slope * t)
    return SkillResult(name, {"removed_slope": float(slope), "slope_unit": f"per {unit}", "detrended": True}, series=out.rename(x.name))


@register("prewhiten")
def prewhiten(x: pd.Series) -> SkillResult:
    """Removes lag-1 autocorrelation: x[t] - r1 * x[t-1], dropping the first point.

    Assumes AR(1) noise on a regular, gap-free, already detrended series; applied
    to a trending series it also shrinks the trend.
    """
    name = "prewhiten"
    if (r := guard(name, x, 12)) is not None:
        return r
    r1 = float(acf(x.to_numpy(dtype=float), nlags=1, fft=False)[1])
    out = (x - r1 * x.shift(1)).iloc[1:]
    return SkillResult(name, {"lag1_autocorrelation": r1, "prewhitened": True}, series=out.rename(x.name))
