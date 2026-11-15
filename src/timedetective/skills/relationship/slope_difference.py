"""Is one series changing faster than another?"""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from timedetective.skills.checks import time_axis
from timedetective.skills.registry import register
from timedetective.skills.relationship.align import guard_pair
from timedetective.skills.result import SkillResult


@register("slope_difference")
def slope_difference(x: pd.Series, y: pd.Series, alpha: float = 0.05) -> SkillResult:
    """Trend of the paired difference x - y, with Newey-West standard errors.

    Differencing removes noise the two series share (e.g. two neighbourhoods
    under the same weather), so this is sharper than comparing two separate
    intervals. Assumes linear trends; two aligned, regular, gap-free series.
    """
    name = "slope_difference"
    if (r := guard_pair(name, x, y, 20)) is not None:
        return r
    t, unit = time_axis(x)
    design = sm.add_constant(t)
    lags = int(np.floor(4 * (len(x) / 100) ** (2 / 9)))
    fit = sm.OLS((x - y).to_numpy(dtype=float), design).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    slope_x = float(sm.OLS(x.to_numpy(dtype=float), design).fit().params[1])
    slope_y = float(sm.OLS(y.to_numpy(dtype=float), design).fit().params[1])
    lo, hi = fit.conf_int(alpha)[1]
    return SkillResult(name, {
        "slope_x": slope_x,
        "slope_y": slope_y,
        "slope_difference": float(fit.params[1]),
        "slope_unit": f"per {unit}",
        "ci_low": float(lo),
        "ci_high": float(hi),
        "p_value": float(fit.pvalues[1]),
        "slopes_differ": bool(fit.pvalues[1] < alpha),
        "opposite_sign": bool(slope_x * slope_y < 0),
        "alpha": alpha,
    })
