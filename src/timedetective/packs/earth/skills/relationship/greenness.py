"""Does the region's greenness show the change in its stored water?"""

import pandas as pd
from scipy.stats import spearmanr

from timedetective.packs.earth.skills.common import plain
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse
from timedetective.skills.trend.mann_kendall import mann_kendall_prewhitened
from timedetective.skills.trend.sens_slope import sens_slope

MIN_YEARS = 12
MIN_MONTHS_PER_YEAR = 10


def yearly_greenness(vegetation: pd.Series) -> pd.Series:
    """Calendar-year mean of monthly means; a year with fewer than ten observed months is left out."""
    monthly = vegetation.resample("MS").mean()
    grouped = monthly.groupby(monthly.index.year)
    yearly = grouped.mean()[grouped.count() >= MIN_MONTHS_PER_YEAR]
    yearly.index = pd.to_datetime(yearly.index.astype(str), format="%Y")
    return yearly


@register("storage_greenness")
def storage_greenness(annual: pd.Series, vegetation: pd.Series | None, prior_values: dict,
                      trend_values: dict) -> SkillResult:
    """Set the region's yearly greenness beside its yearly water storage, over the same years.

    Assumes a vegetation-index record for the same region. Reports the greenness trend (Sen
    slope, prewhitened Mann-Kendall) and the rank correlation with storage, and names one of
    four patterns. "Greenness held while storage fell" is named only when the storage decline
    passed the project's significance test. This is a description of two records side by
    side; it does not test why storage changed (Asoka and Mishra 2020 link the pattern in
    north-west India to pumping for irrigation; this step does not test that).
    """
    name = "storage_greenness"
    if vegetation is None:
        return refuse(name, "no vegetation record was supplied", "supply a vegetation index for the same region")
    if vegetation.attrs.get("variable") != "vegetation_index":
        return refuse(name, "the record is not a vegetation index", "supply a vegetation index such as NDVI")
    if not isinstance(vegetation.index, pd.DatetimeIndex):
        return refuse(name, "the vegetation record has no dates", "supply a dated vegetation record")
    green = yearly_greenness(vegetation.dropna())
    storage = annual.copy()
    storage.index = pd.to_datetime(storage.index.year.astype(str), format="%Y")
    years = storage.index.intersection(green.index)
    if len(years) < MIN_YEARS:
        return refuse(name, f"only {len(years)} years have both storage and ten or more months of greenness",
                      f"use records that overlap for at least {MIN_YEARS} years")
    green, storage = green.loc[years], storage.loc[years]
    slope, test = sens_slope(green), mann_kendall_prewhitened(green)
    for part in (slope, test):
        if not part.ok:
            return refuse(name, part.refusal.failed, part.refusal.would_change)
    rho, rho_p = spearmanr(storage.to_numpy(dtype=float), green.to_numpy(dtype=float))
    greening = bool(test.values["trend_detected"]) and test.values["direction"] == "increasing"
    browning = bool(test.values["trend_detected"]) and test.values["direction"] == "decreasing"
    storage_falls = bool(trend_values["trend_detected"]) and trend_values["slope_cm_per_year"] < 0
    per_decade = 10 * slope.values["slope"]
    first, last = int(years[0].year), int(years[-1].year)
    if storage_falls and greening:
        pattern = "greener_while_storage_fell"
        sentence = (f"Over the same years ({first}-{last}) the region grew greener, by about {per_decade:.2f} NDVI a decade. "
                    "Looking at the fields alone, nothing would suggest the water under them was falling.")
    elif storage_falls and not browning:
        pattern = "green_held_while_storage_fell"
        sentence = (f"Over the same years ({first}-{last}) the region's greenness showed no detectable decline "
                    f"(about {per_decade:+.2f} NDVI a decade, not distinguishable from no change). "
                    "Looking at the fields alone, nothing would suggest the water under them was falling.")
    elif storage_falls:
        pattern = "both_fell"
        sentence = f"Over the same years ({first}-{last}) the region's greenness also declined, by about {abs(per_decade):.2f} NDVI a decade."
    else:
        pattern = "no_tested_decline"
        sentence = ("Storage did not show a tested decline, so there is no hidden fall for greenness to mask; "
                    f"greenness {'rose' if greening else 'fell' if browning else 'showed no clear trend'} over {first}-{last}.")
    prior = prior_values["conclusion"]
    limits = list(prior.get("limits", []))
    excluded = vegetation.attrs.get("excluded_mascons") or []
    if excluded:
        share = (vegetation.attrs.get("spatial_support") or {}).get("share_of_storage_region_area")
        limits.append(f"Greenness leaves out {len(excluded)} of the region's blocks"
                      + (f" ({100 * (1 - share):.0f}% of its area)" if share else "")
                      + ", which cloud or snow hide in more than a quarter of months.")
    if pattern in ("greener_while_storage_fell", "green_held_while_storage_fell"):
        limits.append("Fields staying green while stored water falls is the pattern a reference study of north-west India "
                      "links to pumping for irrigation; this check shows the two records side by side and does not test that cause.")
    return SkillResult(name, plain({
        "pattern": pattern, "n_years": len(years), "first_year": first, "last_year": last,
        "greenness_slope_per_decade": per_decade,
        "greenness_interval_per_decade": [10 * slope.values["ci_low"], 10 * slope.values["ci_high"]],
        "greenness_trend_detected": bool(test.values["trend_detected"]), "greenness_direction": test.values["direction"],
        "greenness_p_value": test.values["p_value"],
        "spearman_storage_greenness": float(rho), "spearman_p_value": float(rho_p),
        "spearman_note": "when both records trend, this mostly reflects the two trends; it is not evidence of a link",
        "yearly": [{"year": int(y.year), "greenness": float(g), "storage_cm": float(s)}
                   for y, g, s in zip(years, green, storage)],
        "vegetation_product": vegetation.attrs.get("product"), "excluded_mascons": excluded,
        "method": "calendar-year mean greenness; Sen slope and prewhitened Mann-Kendall; Spearman rank correlation; descriptive",
        "conclusion": {**prior, "statement": f"{prior['statement']} {sentence}", "limits": limits,
                       "evidence": {**prior["evidence"], "greenness_pattern": pattern}}}))
