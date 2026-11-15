"""Put a series on a fixed cadence."""

import numpy as np
import pandas as pd

from timedetective.skills.checks import guard
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("regularize")
def regularize(x: pd.Series, freq: str = "MS", how: str = "mean", min_count: int = 1) -> SkillResult:
    """Aggregate to a regular grid at `freq` ("MS" monthly, "D" daily, "YS" yearly).

    Assumes a datetime index. Periods with fewer than `min_count` observations
    become NaN (use it to drop years with too few months); it never upsamples,
    so a target cadence finer than the data is refused.
    """
    name = "regularize"
    if (r := guard(name, x, 2, allow_missing=True, need_regular=False, allow_constant=True)) is not None:
        return r
    if not isinstance(x.index, pd.DatetimeIndex):
        return refuse(name, "the series has no datetime index", "attach timestamps before regularizing")
    if how not in ("mean", "sum", "median", "max", "min"):
        return refuse(name, f"unknown aggregation {how!r}", "use mean, sum, median, max or min")
    x = x.sort_index()
    grid = x.resample(freq)
    median_spacing = np.median(np.diff(x.index.values).astype("timedelta64[s]").astype(float))
    target_spacing = np.median(np.diff(grid.size().index.values).astype("timedelta64[s]").astype(float)) if len(grid.size()) > 1 else np.inf
    if target_spacing < 0.9 * median_spacing:
        return refuse(name, f"target cadence {freq!r} is finer than the data", "choose a coarser cadence; this never upsamples")
    out = getattr(grid, how)() if how != "sum" else grid.sum(min_count=1)
    out = out.where(grid.count() >= max(1, min_count)).rename(x.name)
    return SkillResult(name, {"cadence": freq, "aggregation": how, "min_count": min_count, "n": len(out), "n_missing": int(out.isna().sum())}, series=out)
