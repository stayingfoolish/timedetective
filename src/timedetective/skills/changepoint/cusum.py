"""CUSUM test for a drift in the mean."""

import numpy as np
import pandas as pd
from statsmodels.stats.diagnostic import breaks_cusumolsresid

from timedetective.skills.checks import guard
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult


@register("cusum")
def cusum(x: pd.Series, alpha: float = 0.05) -> SkillResult:
    """Cumulative-sum test that the mean is constant, with the point of largest departure.

    Assumes a regular, gap-free series with no trend and little serial correlation
    (run on residuals otherwise). `break_position` is the first position after the peak.
    """
    name = "cusum"
    if (r := guard(name, x, 20)) is not None:
        return r
    e = x.to_numpy(dtype=float) - float(x.mean())
    stat, p, _ = breaks_cusumolsresid(e, ddof=1)
    k = int(np.argmax(np.abs(np.cumsum(e)[:-1])))
    return SkillResult(name, {
        "break_detected": bool(p < alpha),
        "break_position": k + 1,
        "break_time": x.index[k + 1],
        "statistic": float(stat),
        "p_value": float(p),
        "alpha": alpha,
    })
