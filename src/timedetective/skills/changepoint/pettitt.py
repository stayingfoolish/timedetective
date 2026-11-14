"""Pettitt's rank test for a single shift in level."""

import numpy as np
import pandas as pd

from timedetective.skills.checks import guard
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult


@register("pettitt")
def pettitt(x: pd.Series, alpha: float = 0.05) -> SkillResult:
    """Tests for one change point in the median and locates it.

    Statistic (Pettitt 1979): U_t = sum_{i<=t} sum_{j>t} sign(x_j - x_i),
    K = max|U_t|, p ~= 2 exp(-6 K^2 / (n^3 + n^2)). Assumes independent
    observations and at most one shift; a steady trend also triggers it.
    `break_position` is the first position of the later segment.
    """
    name = "pettitt"
    if (r := guard(name, x, 20)) is not None:
        return r
    v = x.to_numpy(dtype=float)
    n = len(v)
    ranks = pd.Series(v).rank().to_numpy()
    # Equivalent rank form: U_t = t(n+1) - 2 * sum_{i<=t} rank_i, sign-flipped to match the definition above.
    u = 2 * np.cumsum(ranks)[:-1] - np.arange(1, n) * (n + 1)
    u = -u
    k = int(np.argmax(np.abs(u)))
    stat = float(np.abs(u[k]))
    p = float(min(1.0, 2 * np.exp(-6 * stat**2 / (n**3 + n**2))))
    return SkillResult(name, {
        "break_detected": bool(p < alpha),
        "break_position": k + 1,
        "break_time": x.index[k + 1],
        "statistic": stat,
        "p_value": p,
        "median_before": float(np.median(v[: k + 1])),
        "median_after": float(np.median(v[k + 1 :])),
        "alpha": alpha,
    })
