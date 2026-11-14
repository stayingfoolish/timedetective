"""Does the trend survive a different start or end date?"""

import numpy as np
import pandas as pd
from scipy import stats

from timedetective.skills.checks import guard, time_axis
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("period_sensitivity")
def period_sensitivity(x: pd.Series, max_trim: float = 0.2, n_steps: int = 5) -> SkillResult:
    """Theil-Sen slope recomputed after trimming up to `max_trim` of the record from
    the start, the end, or both, on an `n_steps` grid.

    `sign_stable` is true when every sub-period has the full record's sign.
    Assumes a regular, gap-free series. A trend that flips sign when a few
    years are dropped depends on the choice of dates.
    """
    name = "period_sensitivity"
    if not 0 < max_trim < 0.5 or n_steps < 1:
        return refuse(name, "need 0 < max_trim < 0.5 and n_steps >= 1", "pass a trim fraction below one half")
    if (r := guard(name, x, 30)) is not None:
        return r
    t, unit = time_axis(x)
    y = x.to_numpy(dtype=float)
    n = len(y)
    full = float(stats.theilslopes(y, t)[0])
    trims = sorted({int(round(f * n)) for f in np.linspace(0, max_trim, n_steps + 1)})
    slopes = [
        float(stats.theilslopes(y[a : n - b], t[a : n - b])[0])
        for a in trims for b in trims if (a, b) != (0, 0)
    ]
    same = [s * full > 0 for s in slopes]
    return SkillResult(name, {
        "slope_full": full,
        "slope_min": float(min(slopes)),
        "slope_max": float(max(slopes)),
        "slope_unit": f"per {unit}",
        "n_subperiods": len(slopes),
        "share_same_sign": float(np.mean(same)),
        "sign_stable": bool(all(same)),
        "max_trim": max_trim,
    })
