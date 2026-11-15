"""Second indicator for the season check: was rainfall unusual in the same season?"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from timedetective.packs.earth.skills.common import ordinal, plain, season_table, standing, valid_months
from timedetective.packs.earth.skills.transforms.monthly import weather_monthly
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse

LOW, HIGH = 25.0, 75.0


@register("season_rainfall")
def season_rainfall(monthly: pd.Series, rainfall: pd.Series | None, standing_values: dict,
                    season_months: list[int], target_year: int, lead_months: int = 1) -> SkillResult:
    """Rank the season's rainfall and say whether it agrees with the vegetation reading.

    Rainfall is totalled over the season months moved `lead_months` earlier, because
    vegetation responds after rain. The lead is declared, not fitted; correlations for
    leads 0 to 3 are reported so a poor choice is visible. Agreement of two indicators
    is evidence, not proof: both can share errors.
    """
    name = "season_rainfall"
    if rainfall is None:
        return refuse(name, "no rainfall record was supplied", "supply rainfall for the same place to check a second indicator")
    if not valid_months(season_months) or lead_months not in (0, 1, 2, 3):
        return refuse(name, "invalid season months or lead", "declare consecutive months and a lead of 0 to 3 months")
    if rainfall.attrs.get("variable") != "precipitation":
        return refuse(name, "the second record is not precipitation", "supply a precipitation record")
    converted = weather_monthly(rainfall)
    if not converted.ok:
        return refuse(name, converted.refusal.failed, converted.refusal.would_change)
    rain = converted.series
    used = list(standing_values["months_used"])
    veg = pd.Series({row["year"]: row["value"] for row in standing_values["seasons"]})

    def totals(lead: int) -> pd.Series:
        months = [(m - 1 - lead) % 12 + 1 for m in used]
        table = season_table(rain, months)
        # A season is labelled by the year of its first vegetation month; a lead that crosses January shifts the label.
        shift = int(months[0] > used[0])
        out = table.dropna().sum(axis=1)
        out.index = out.index + shift
        return out

    rain_seasons = totals(lead_months)
    if target_year not in rain_seasons.index:
        return refuse(name, f"rainfall is not available for the whole {target_year} window",
                      "wait for a finished, quality-controlled rainfall record for this season")
    common = rain_seasons.index.intersection(veg.index)
    if len(common) < 10:
        return refuse(name, f"only {len(common)} seasons have both records", "use longer records")
    rain_common = rain_seasons.loc[common]
    value = float(rain_common.loc[target_year])
    rank = int((rain_common < value).sum()) + 1
    percentile, band = standing(rank, len(common))
    by_lead = {}
    for lead in range(4):
        series = totals(lead)
        both = series.index.intersection(veg.index)
        if len(both) >= 10:
            rho, p = spearmanr(series.loc[both], veg.loc[both])
            by_lead[str(lead)] = {"spearman_rho": float(rho), "p_value": float(p), "n": len(both)}
    link = by_lead.get(str(lead_months), {})
    moves_together = bool(link and link["spearman_rho"] > 0 and link["p_value"] < 0.05)
    # Where the vegetation record drifts, compare rainfall with the drift-adjusted standing.
    veg_pct = float(standing_values.get("percentile_for_comparison", standing_values["percentile"]))
    if veg_pct <= LOW and percentile <= LOW:
        agreement, agreeing = "both_low", 2
    elif veg_pct >= HIGH and percentile >= HIGH:
        agreement, agreeing = "both_high", 2
    elif LOW < veg_pct < HIGH and LOW < percentile < HIGH:
        agreement, agreeing = "both_usual", 2
    else:
        agreement, agreeing = "differ", 1
    position = "lowest" if rank == 1 else "highest" if rank == len(common) else f"{ordinal(rank)} lowest"
    sentence = {"both_low": "Rainfall agrees", "both_high": "Rainfall agrees", "both_usual": "Rainfall agrees",
                "differ": "Rainfall does not show the same thing"}[agreement]
    statement = (f"{standing_values['conclusion']['statement']} {sentence}: rainfall for the matching months was "
                 f"{band} ({position} of {len(common)} seasons, {value:.0f} mm).")
    limits = list(standing_values["conclusion"]["limits"])
    if not moves_together:
        limits.insert(0, "In this record, season rainfall and greenness do not clearly move together, so rainfall is a weak cross-check here.")
    return SkillResult(name, plain({
        "rainfall_total_mm": value, "rank": rank, "n_seasons": len(common), "percentile": percentile, "band": band,
        "lead_months": lead_months, "rainfall_months": [(m - 1 - lead_months) % 12 + 1 for m in used],
        "agreement": agreement, "rainfall_and_greenness_move_together": moves_together, "by_lead": by_lead,
        "rainfall_product": rain.attrs.get("product"), "units": "mm per season window",
        "seasons": [{"year": int(y), "rainfall_mm": float(v)} for y, v in rain_common.items()],
        "conclusion": {
            "statement_type": "season_standing", "statement": statement, "limits": limits,
            "evidence": {"indicators_agreeing": agreeing, "indicators_checked": 2},
            "would_strengthen": ["A cropland mask and crop calendar, so the reading covers fields only.",
                                 "Reports from the ground.",
                                 "A rainfall record measured independently of the satellite and model products."]}}))
