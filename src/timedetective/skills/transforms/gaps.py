"""Fill short gaps; refuse long ones."""

import numpy as np
import pandas as pd

from timedetective.skills.checks import guard, phase
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("gap_fill")
def gap_fill(x: pd.Series, max_gap: int = 2, period: int | None = None) -> SkillResult:
    """Linear interpolation of gaps up to `max_gap` steps; with `period`, interpolates
    the departures from the mean seasonal cycle instead of the raw values.

    Assumes a regular index with gaps stored as NaN. A gap longer than `max_gap`,
    or a gap at either end, is refused rather than filled.
    """
    name = "gap_fill"
    if (r := guard(name, x, 3, allow_missing=True)) is not None:
        return r
    missing = x.isna().to_numpy()
    if not missing.any():
        return SkillResult(name, {"n_filled": 0, "longest_gap": 0}, series=x.copy())
    if missing[0] or missing[-1]:
        return refuse(name, "the series starts or ends with a gap", "trim the record to its first and last observation")
    edges = np.diff(np.concatenate([[0], missing.astype(int), [0]]))
    longest = int((np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1)).max())
    if longest > max_gap:
        return refuse(
            name,
            f"longest gap is {longest} steps; the limit is {max_gap}",
            "analyse the segments separately, or use a procedure that tolerates gaps",
        )
    if period:
        ph = phase(x, period)
        cycle = x.groupby(ph).mean().reindex(range(period))
        if cycle.isna().any():
            return refuse(name, "some phases of the cycle have no observations", "fill without `period`, or use a longer record")
        clim = pd.Series(cycle.to_numpy()[ph], index=x.index)
        out = (x - clim).interpolate("linear") + clim
    else:
        out = x.interpolate("linear")
    return SkillResult(name, {"n_filled": int(missing.sum()), "longest_gap": longest}, series=out.rename(x.name))
