"""Season check: how unusual is a growing season in this place's own record?

Information only. These procedures describe a vegetation reading against earlier
seasons at the same place. They do not identify crops, estimate yield or declare a failure.
"""

import numpy as np
import pandas as pd

from timedetective.packs.earth.skills.common import metadata_problem, ordinal, plain, season_table, standing, valid_months
from timedetective.skills.changepoint.segmented import step_vs_trend
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse
from scipy.stats import theilslopes

from timedetective.skills.trend.sens_slope import sens_slope

MIN_SEASONS = 10


@register("season_audit")
def season_audit(x: pd.Series, season_months: list[int], target_year: int, not_answered: list[str] | None = None) -> SkillResult:
    """Check provenance, value range and that the question fits the record; never repairs data."""
    name = "season_audit"
    if (problem := metadata_problem(x, "vegetation_index")) is not None:
        return refuse(name, *problem)
    if not valid_months(season_months):
        return refuse(name, "season months must be consecutive calendar months, e.g. [4, 5, 6, 7, 8, 9]",
                      "declare the growing season for this place; it is not inferred from the data")
    values = x.to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    if len(finite) < 24 or (finite < -0.2).any() or (finite > 1.0).any():
        return refuse(name, "too few valid readings, or values outside the range of a vegetation index (-0.2 to 1)",
                      "check units and scaling, or use a longer record")
    years = sorted(set(x.index.year[np.isfinite(values)]))
    if not isinstance(target_year, int) or isinstance(target_year, bool) or not years[0] <= target_year <= years[-1]:
        return refuse(name, f"the record covers {years[0]} to {years[-1]}; {target_year} is outside it",
                      "choose a season the record contains")
    return SkillResult(name, plain({
        "n_readings": len(x), "n_missing": int(len(x) - len(finite)), "start": x.index[0], "end": x.index[-1],
        "season_months": list(season_months), "target_year": target_year, "units": x.attrs["units"],
        "product": x.attrs["product"], "spatial_support": x.attrs["spatial_support"],
        "quality": x.attrs.get("quality", "not stated"), "known_issues": x.attrs.get("known_issues", []),
        "not_answered": list(not_answered or []),
        "scope": "vegetation in the declared area, all land cover together; not a crop map"}))


@register("season_standing")
def season_standing(monthly: pd.Series, season_months: list[int], target_year: int, audit_values: dict | None = None) -> SkillResult:
    """Rank the target season against the same months of every other season on record.

    Uses the season months that have a reading in the target year (all of them for a
    finished season, the months so far for one in progress) and only compares seasons
    that have every one of those months. Rank 1 is the lowest. Assumes the place and
    the instrument are comparable across years; a drift in the record is reported, not removed.
    """
    name = "season_standing"
    if not valid_months(season_months):
        return refuse(name, "invalid season months", "declare consecutive calendar months")
    table = season_table(monthly, list(season_months))
    if target_year not in table.index:
        return refuse(name, f"no readings in the {target_year} season", "choose a season the record contains")
    used = [m for m in season_months if np.isfinite(table.loc[target_year, m])]
    if not used:
        return refuse(name, f"no valid readings in the {target_year} season", "wait for data, or check the quality screening")
    if used != list(season_months[: len(used)]):
        return refuse(name, "a month in the middle of the target season has no valid reading",
                      "this procedure does not fill gaps; choose another season or a wider area")
    seasons = table[used].dropna().mean(axis=1)
    n = len(seasons)
    if n < MIN_SEASONS:
        return refuse(name, f"only {n} comparable seasons on record; {MIN_SEASONS} are needed", "use a longer record")
    value = float(seasons.loc[target_year])
    others = seasons.drop(target_year)
    rank = int((seasons < value).sum()) + 1
    percentile, band = standing(rank, n)
    spread = float(others.std(ddof=1))
    low, high = float(seasons.min()), float(seasons.max())
    complete = len(used) == len(season_months)
    drift = {"checked": False, "reason": "seasons are not consecutive"}
    yearly = pd.Series(seasons.to_numpy(), index=pd.to_datetime(seasons.index.astype(str), format="%Y"))
    if len(yearly) >= 12 and (np.diff(seasons.index.to_numpy()) == 1).all():
        model, slope = step_vs_trend(yearly), sens_slope(yearly)
        if model.ok and slope.ok:
            drift = {"checked": True, "best_model": model.values["best_model"],
                     "record_drifts": model.values["best_model"] != "flat",
                     "sen_slope_per_decade": 10 * slope.values["slope"],
                     "slope_interval_per_decade": [10 * slope.values["ci_low"], 10 * slope.values["ci_high"]]}
    position = "lowest" if rank == 1 else "highest" if rank == n else f"{ordinal(rank)} lowest"
    span = f"{seasons.index.min()}-{seasons.index.max()}"
    months_text = "the whole season" if complete else f"the first {len(used)} of {len(season_months)} season months"
    statement = (f"Vegetation greenness in the {target_year} season was {band}: {position} of {n} seasons "
                 f"({span}), comparing {months_text}.")
    limits = ["This is all vegetation in the area, not crops alone.",
              "It describes how unusual the season is here; it does not estimate a harvest or say why."]
    adjusted = None
    if drift.get("record_drifts"):
        # The record has been drifting, so also rank the season against a straight line fitted through the other seasons.
        years = seasons.index.to_numpy(dtype=float)
        slope, intercept = theilslopes(others.to_numpy(), others.index.to_numpy(dtype=float))[:2]
        residual = seasons - (intercept + slope * years)
        adjusted_rank = int((residual < residual.loc[target_year]).sum()) + 1
        adjusted_percentile, adjusted_band = standing(adjusted_rank, n)
        adjusted = {"rank": adjusted_rank, "percentile": adjusted_percentile, "band": adjusted_band,
                    "method": "rank of the departure from a Theil-Sen line fitted to the other seasons"}
        direction = "upward" if slope > 0 else "downward"
        place = "lowest" if adjusted_rank == 1 else "highest" if adjusted_rank == n else f"{ordinal(adjusted_rank)} lowest"
        statement += (f" Greenness here has drifted {direction} over the record; measured against that drift, "
                      f"the season was {adjusted_band} ({place} of {n}).")
        limits.insert(0, "Because the record drifts, 'usual' is a moving reference; the drift itself is not explained here.")
    limits += list((audit_values or {}).get("not_answered", []))
    return SkillResult(name, plain({
        "target_year": target_year, "value": value, "rank": rank, "n_seasons": n, "percentile": percentile,
        "band": band, "lowest_on_record": rank == 1, "highest_on_record": rank == n,
        "mean_of_other_seasons": float(others.mean()),
        "z_against_other_seasons": (value - float(others.mean())) / spread if spread > 0 else None,
        "condition_index": 100 * (value - low) / (high - low) if high > low else None,
        "months_used": used, "season_complete": complete, "comparable_years": seasons.index.tolist(),
        "seasons": [{"year": int(y), "value": float(v)} for y, v in seasons.items()], "drift": drift,
        "drift_adjusted": adjusted, "percentile_for_comparison": adjusted["percentile"] if adjusted else percentile,
        "conclusion": {
            "statement_type": "season_standing", "statement": statement, "limits": limits,
            "evidence": {"indicators_agreeing": 1, "indicators_checked": 1},
            "would_strengthen": ["A second indicator, such as rainfall for the same season.",
                                 "A cropland mask and crop calendar, so the reading covers fields only.",
                                 "Reports from the ground."]}}))
