"""How this point in the cycle compares with the same point in earlier cycles."""

import numpy as np
import pandas as pd

from timedetective.skills.checks import guard, phase
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


def _by_phase(name: str, x: pd.Series, period: int, min_cycles: int):
    """Per-phase groups, or a refusal when the record holds too few cycles."""
    if period < 2:
        return refuse(name, f"period must be at least 2, got {period}", "pass the seasonal period")
    if (r := guard(name, x, min_cycles * period, allow_missing=True)) is not None:
        return r
    ph = pd.Series(phase(x, period), index=x.index)
    counts = x.groupby(ph).count().reindex(range(period), fill_value=0)
    if counts.min() < min_cycles:
        return refuse(
            name,
            f"some points in the cycle have only {int(counts.min())} past observations; {min_cycles} are needed",
            "use a longer record, or a coarser cadence",
        )
    return ph


@register("standardized_anomaly")
def standardized_anomaly(x: pd.Series, period: int = 12, min_cycles: int = 5) -> SkillResult:
    """Each value as a z-score against the same phase of the cycle in all years: (x - mean) / sd.

    Assumes a regular index and that years are comparable (no trend or sensor
    change in the record; otherwise early and late years are not on one scale).
    Tolerates gaps. With few cycles the mean and sd are rough, so `n_cycles` is
    reported; `min_cycles` is a house minimum, not a published rule.
    """
    name = "standardized_anomaly"
    ph = _by_phase(name, x, period, min_cycles)
    if isinstance(ph, SkillResult):
        return ph
    grouped = x.groupby(ph)
    mean, sd = grouped.transform("mean"), grouped.transform(lambda v: v.std(ddof=1))
    if (sd == 0).any():
        return refuse(name, "a point in the cycle has no variation across years", "nothing to standardize against")
    z = ((x - mean) / sd).rename(x.name)
    latest = z.dropna()
    return SkillResult(
        name,
        {
            "latest_z": float(latest.iloc[-1]),
            "latest_time": latest.index[-1],
            "n_cycles": int(grouped.count().min()),
            "period": period,
        },
        series=z,
    )


@register("condition_index")
def condition_index(x: pd.Series, period: int = 12, min_cycles: int = 5) -> SkillResult:
    """Each value scaled between the lowest (0) and highest (100) ever seen at that phase of the cycle.

    The form used for the Vegetation Condition Index. Same assumptions as
    `standardized_anomaly`. The record's own extremes define the scale, so one
    outlier year changes every later reading and a short record flatters the present.
    """
    name = "condition_index"
    ph = _by_phase(name, x, period, min_cycles)
    if isinstance(ph, SkillResult):
        return ph
    grouped = x.groupby(ph)
    low, high = grouped.transform("min"), grouped.transform("max")
    if (high == low).any():
        return refuse(name, "a point in the cycle has no variation across years", "nothing to scale against")
    index = (100 * (x - low) / (high - low)).rename(x.name)
    latest = index.dropna()
    return SkillResult(
        name,
        {
            "latest_index": float(latest.iloc[-1]),
            "latest_time": latest.index[-1],
            "n_cycles": int(grouped.count().min()),
            "period": period,
        },
        series=index,
    )
