"""Where the current season-to-date stands among the same stretch of earlier seasons."""

import numpy as np
import pandas as pd

from timedetective.skills.checks import guard, phase
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("seasonal_rank")
def seasonal_rank(
    x: pd.Series, period: int = 12, season_start: int = 0, season_length: int | None = None, min_seasons: int = 5
) -> SkillResult:
    """Ranks the mean of the current season so far against the same window in every earlier season.

    `season_start` is the phase (0-based; calendar month minus 1 for monthly data)
    at which the season begins, `season_length` its length in steps (default: the
    whole cycle). Rank 1 is the lowest on record. Assumes a regular, gap-free
    series and comparable years. This describes how unusual the season is in
    this record; it does not say why, or what it means for a harvest.
    """
    name = "seasonal_rank"
    length = period if season_length is None else season_length
    if period < 2 or not 0 <= season_start < period or not 1 <= length <= period:
        return refuse(name, "need period >= 2, 0 <= season_start < period and 1 <= season_length <= period", "pass a valid season definition")
    if (r := guard(name, x, min_seasons * period)) is not None:
        return r
    offset = (phase(x, period) - season_start) % period
    upto = int(offset[-1])
    if upto >= length:
        return refuse(
            name,
            "the latest observation falls outside the growing season",
            "ask again once the season has started, or rank a completed season by trimming the series to its end",
        )
    season_id = np.cumsum(offset == 0)
    in_window = offset <= upto
    frame = pd.DataFrame({"v": x.to_numpy(dtype=float)[in_window], "s": season_id[in_window]})
    seasons = frame.groupby("s")["v"].agg(["mean", "count"])
    seasons = seasons[(seasons["count"] == upto + 1) & (seasons.index > 0)]
    if len(seasons) < min_seasons:
        return refuse(
            name,
            f"only {len(seasons)} comparable seasons on record; {min_seasons} are needed",
            "use a longer record",
        )
    current, past = float(seasons["mean"].iloc[-1]), seasons["mean"].iloc[:-1]
    rank = int((seasons["mean"] < current).sum()) + 1
    n = len(seasons)
    return SkillResult(name, {
        "season_to_date_mean": current,
        "rank": rank,
        "n_seasons": n,
        "percentile": float(100 * (rank - 0.5) / n),
        "lowest_on_record": rank == 1,
        "highest_on_record": rank == n,
        "past_mean": float(past.mean()),
        "z_against_past": float((current - past.mean()) / past.std(ddof=1)) if past.std(ddof=1) > 0 else None,
        "steps_into_season": upto + 1,
        "season_start_time": x.index[len(x) - 1 - upto],
    })
