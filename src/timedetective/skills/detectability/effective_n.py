"""How many independent observations a record is worth."""

import pandas as pd
from statsmodels.tsa.stattools import acf

from timedetective.skills.checks import guard
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult


@register("effective_sample_size")
def effective_sample_size(x: pd.Series) -> SkillResult:
    """n * (1 - r1) / (1 + r1) for lag-1 autocorrelation r1 > 0, else n.

    Assumes AR(1)-like memory in a regular, gap-free, detrended series; on a
    trending series r1 is inflated and the result is too small.
    """
    name = "effective_sample_size"
    if (r := guard(name, x, 12)) is not None:
        return r
    n = len(x)
    r1 = float(acf(x.to_numpy(dtype=float), nlags=1, fft=False)[1])
    n_eff = n * (1 - r1) / (1 + r1) if r1 > 0 else float(n)
    return SkillResult(name, {"n": n, "lag1_autocorrelation": r1, "effective_n": float(n_eff), "effective_share": float(n_eff / n)})
