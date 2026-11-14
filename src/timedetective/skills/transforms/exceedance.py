"""Turn a daily series into a yearly count of threshold crossings."""

import pandas as pd

from timedetective.skills.checks import guard
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("exceedance_counts")
def exceedance_counts(
    x: pd.Series, threshold: float, above: bool = True, freq: str = "YS", min_coverage: float = 0.9
) -> SkillResult:
    """Number of observations beyond `threshold` in each period of `freq`.

    Assumes a datetime index. Periods observed for less than `min_coverage` of
    the fullest period are set to NaN rather than undercounted.
    """
    name = "exceedance_counts"
    if (r := guard(name, x, 2, allow_missing=True, need_regular=False, allow_constant=True)) is not None:
        return r
    if not isinstance(x.index, pd.DatetimeIndex):
        return refuse(name, "the series has no datetime index", "attach timestamps first")
    hit = ((x > threshold) if above else (x < threshold)).where(x.notna())
    counts = hit.resample(freq).sum(min_count=1)
    observed = x.notna().resample(freq).sum()
    counts = counts.where(observed >= min_coverage * observed.max())
    return SkillResult(
        name,
        {"threshold": threshold, "above": above, "n_periods": len(counts), "n_incomplete": int(counts.isna().sum())},
        series=counts.astype(float).rename(x.name),
    )
