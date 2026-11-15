"""Accumulated versions of a series, for stores that respond to inputs summed over time."""

import pandas as pd

from timedetective.skills.checks import guard
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("rolling_accumulation")
def rolling_accumulation(x: pd.Series, window: int) -> SkillResult:
    """Sum over the trailing `window` steps (e.g. 12-month rainfall); NaN until the window fills.

    Assumes a regular, gap-free series. A store such as groundwater responds to
    inputs accumulated over months to years, not to a single month.
    """
    name = "rolling_accumulation"
    if window < 2:
        return refuse(name, f"window must be at least 2, got {window}", "pass a longer window")
    if (r := guard(name, x, window + 1)) is not None:
        return r
    return SkillResult(name, {"window": window, "accumulated": True}, series=x.rolling(window).sum().rename(x.name))


@register("cumulative_departure")
def cumulative_departure(x: pd.Series, baseline: tuple[str, str] | None = None) -> SkillResult:
    """Running sum of departures from the mean (of the whole record, or of an inclusive `baseline` range).

    Rising stretches are wetter than average, falling stretches drier. Assumes a
    regular, gap-free series. The result always returns to zero at the end when
    the baseline is the whole record, so its endpoints carry no information;
    read the shape, not the level.
    """
    name = "cumulative_departure"
    if (r := guard(name, x, 12)) is not None:
        return r
    base = x.loc[baseline[0] : baseline[1]] if baseline else x
    if len(base) < 2:
        return refuse(name, "the baseline range holds fewer than two observations", "widen the baseline period")
    out = (x - float(base.mean())).cumsum().rename(x.name)
    return SkillResult(
        name,
        {"baseline_mean": float(base.mean()), "baseline_start": base.index[0], "baseline_end": base.index[-1],
         "lowest_time": out.idxmin(), "highest_time": out.idxmax()},
        series=out,
    )
