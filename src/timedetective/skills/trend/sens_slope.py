"""Theil-Sen slope: the median of all pairwise slopes."""

import pandas as pd
from scipy import stats

from timedetective.skills.checks import guard, time_axis
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult


@register("sens_slope")
def sens_slope(x: pd.Series, alpha: float = 0.05) -> SkillResult:
    """Robust slope and confidence interval, insensitive to outliers.

    The interval assumes independent observations (it is too narrow under
    autocorrelation). Assumes a regular, gap-free series.
    """
    name = "sens_slope"
    if (r := guard(name, x, 10)) is not None:
        return r
    t, unit = time_axis(x)
    slope, intercept, lo, hi = stats.theilslopes(x.to_numpy(dtype=float), t, alpha=1 - alpha)
    return SkillResult(name, {
        "slope": float(slope),
        "slope_unit": f"per {unit}",
        "intercept": float(intercept),
        "ci_low": float(lo),
        "ci_high": float(hi),
        "alpha": alpha,
        "n": len(x),
    })
