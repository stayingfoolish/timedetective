"""A trend test that stays honest when the series wanders."""

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

from timedetective.skills.checks import guard, steps_per_unit, time_axis
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult

AGGREGATION_FLOOR = 0.25
CAP = 0.8


@register("drift_test")
def drift_test(x: pd.Series, alpha: float = 0.05, floor: float = AGGREGATION_FLOOR) -> SkillResult:
    """Is the average step-to-step change different from zero, given how much the changes vary?

    A t-test on the first differences. Its standard error is inflated for autocorrelation
    in the changes, using their lag-1 correlation but never less than `floor`. The default
    floor, 0.25, is the correlation that averaging a random walk over each period puts into
    its changes, so the test holds its false-alarm rate when the series is a period-averaged
    random walk. When the noise around a trend is short-lived instead, the changes are
    negatively correlated, the floor over-states their variance, and the test is cautious
    rather than liberal. The price is low power for a weak trend buried in large short-lived
    noise. Assumes a regular, gap-free series; it does not protect against changes that are
    themselves strongly persistent (lag-1 correlation of changes well above 0.5).
    """
    name = "drift_test"
    if (r := guard(name, x, 15)) is not None:
        return r
    d = np.diff(x.to_numpy(dtype=float))
    m = len(d)
    centred = d - d.mean()
    lag1 = float((centred[:-1] * centred[1:]).sum() / (centred * centred).sum())
    rho = min(max(lag1, floor), CAP)
    inflation = float(np.sqrt((1 + rho) / (1 - rho)))
    se = float(d.std(ddof=1) / np.sqrt(m) * inflation)
    stat = float(d.mean() / se)
    p = float(2 * student_t.sf(abs(stat), m - 1))
    detected = p < alpha
    per_unit, unit = steps_per_unit(x), time_axis(x)[1]
    return SkillResult(name, {
        "trend_detected": bool(detected),
        "direction": ("increasing" if d.mean() > 0 else "decreasing") if detected else "no trend",
        "p_value": p, "t": stat, "mean_change_per_step": float(d.mean()), "standard_error": se,
        "mean_change": float(d.mean() * per_unit), "slope_unit": f"per {unit}",
        "lag1_of_changes": lag1, "correlation_used": rho, "inflation": inflation, "alpha": alpha, "n": len(x)})
