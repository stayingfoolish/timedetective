"""Chow test: did the trend line change at a date named in advance?"""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from timedetective.skills.checks import guard, time_axis
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("chow_test")
def chow_test(x: pd.Series, break_at, alpha: float = 0.05, min_segment: int = 5) -> SkillResult:
    """F-test that intercept and slope are the same before and after `break_at`.

    `break_at` is an index label (the first point of the later segment) and must
    be chosen before looking at the data: testing a date picked from the plot
    invalidates the p-value. Assumes uncorrelated residuals.
    """
    name = "chow_test"
    if (r := guard(name, x, 2 * min_segment)) is not None:
        return r
    if break_at not in x.index:
        return refuse(name, f"break_at {break_at!r} is not in the index", "pass a label that exists in the series")
    k = int(x.index.get_loc(break_at))
    if k < min_segment or len(x) - k < min_segment:
        return refuse(name, f"a segment would have fewer than {min_segment} points", "choose a break further from the ends")
    t, unit = time_axis(x)
    y = x.to_numpy(dtype=float)
    after = (np.arange(len(x)) >= k).astype(float)
    pooled = sm.OLS(y, sm.add_constant(t)).fit()
    split = sm.OLS(y, sm.add_constant(np.column_stack([t, after, after * t]))).fit()
    f, p, _ = split.compare_f_test(pooled)
    return SkillResult(name, {
        "break_detected": bool(p < alpha),
        "break_position": k,
        "break_time": x.index[k],
        "f_statistic": float(f),
        "p_value": float(p),
        "slope_before": float(split.params[1]),
        "slope_after": float(split.params[1] + split.params[3]),
        "slope_unit": f"per {unit}",
        "alpha": alpha,
    })
