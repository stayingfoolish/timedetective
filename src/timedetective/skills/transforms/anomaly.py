"""Departures from the mean seasonal cycle."""

import pandas as pd

from timedetective.skills.checks import guard, phase
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("anomaly")
def anomaly(x: pd.Series, period: int = 12, baseline: tuple[str, str] | None = None) -> SkillResult:
    """Subtracts the mean of each phase of the cycle (the climatology).

    `baseline` is an inclusive (start, end) label range used to compute the
    climatology; default is the whole record. Assumes a regular index; tolerates gaps.
    """
    name = "anomaly"
    if period < 2:
        return refuse(name, f"period must be at least 2, got {period}", "pass the seasonal period")
    if (r := guard(name, x, 2 * period, allow_missing=True)) is not None:
        return r
    ph = pd.Series(phase(x, period), index=x.index)
    base = x.loc[baseline[0] : baseline[1]] if baseline else x
    clim = base.groupby(ph.loc[base.index]).mean().reindex(range(period))
    if clim.isna().any():
        return refuse(name, "the baseline does not cover every phase of the cycle", "widen the baseline period")
    out = x - clim.to_numpy()[ph.to_numpy()]
    return SkillResult(
        name,
        {"period": period, "baseline_start": base.index[0], "baseline_end": base.index[-1], "climatology": clim.tolist()},
        series=out.rename(x.name),
    )
