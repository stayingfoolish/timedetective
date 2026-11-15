"""Slope uncertainty by resampling blocks of residuals, which keeps their serial correlation."""

import numpy as np
import pandas as pd

from timedetective.skills.checks import guard, time_axis
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("block_bootstrap_slope")
def block_bootstrap_slope(
    x: pd.Series, *, seed: int, block_length: int | None = None, n_boot: int = 2000, alpha: float = 0.05
) -> SkillResult:
    """Percentile interval for the OLS slope from a moving-block bootstrap of residuals.

    Assumes a linear trend and residual memory shorter than `block_length`
    (default ceil(n^(1/3))). `seed` is required: the same seed gives the same interval.
    """
    name = "block_bootstrap_slope"
    if (r := guard(name, x, 30)) is not None:
        return r
    n = len(x)
    block = block_length or int(np.ceil(n ** (1 / 3)))
    if not 1 <= block <= n // 2:
        return refuse(name, f"block_length {block} is outside [1, n/2]", "pass a block length shorter than half the record")
    t, unit = time_axis(x)
    y = x.to_numpy(dtype=float)
    slope, intercept = np.polyfit(t, y, 1)
    fitted = intercept + slope * t
    resid = y - fitted
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n - block + 1, size=(n_boot, int(np.ceil(n / block))))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_boot, -1)[:, :n]
    tc = t - t.mean()
    slopes = ((fitted + resid[idx]) @ tc) / (tc @ tc)
    lo, hi = np.quantile(slopes, [alpha / 2, 1 - alpha / 2])
    return SkillResult(name, {
        "slope": float(slope),
        "slope_unit": f"per {unit}",
        "ci_low": float(lo),
        "ci_high": float(hi),
        "alpha": alpha,
        "block_length": block,
        "n_boot": n_boot,
        "seed": seed,
    })
