"""Is a straight line an adequate description of the trend?"""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from timedetective.skills.checks import guard, time_axis
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult


@register("linearity_check")
def linearity_check(x: pd.Series, alpha: float = 0.05) -> SkillResult:
    """F-test of a quadratic term added to a linear trend.

    Assumes uncorrelated residuals (the test rejects too often otherwise) and a
    regular, gap-free series. `curved` means a straight line leaves out real curvature.
    """
    name = "linearity_check"
    if (r := guard(name, x, 15)) is not None:
        return r
    t, _ = time_axis(x)
    tc = t - t.mean()
    y = x.to_numpy(dtype=float)
    linear = sm.OLS(y, sm.add_constant(tc)).fit()
    quadratic = sm.OLS(y, sm.add_constant(np.column_stack([tc, tc**2]))).fit()
    f, p, _ = quadratic.compare_f_test(linear)
    return SkillResult(name, {
        "curved": bool(p < alpha),
        "f_statistic": float(f),
        "p_value": float(p),
        "quadratic_coefficient": float(quadratic.params[2]),
        "alpha": alpha,
    })
