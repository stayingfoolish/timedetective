"""Does the change in water storage follow rainfall?"""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from timedetective.packs.earth.skills.common import plain
from timedetective.packs.earth.skills.transforms.monthly import weather_monthly
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse
from timedetective.skills.transforms.accumulate import rolling_accumulation
from timedetective.skills.trend.mann_kendall import mann_kendall_prewhitened
from timedetective.skills.trend.sens_slope import sens_slope

MIN_PAIRS = 12


@register("storage_rainfall")
def storage_rainfall(annual: pd.Series, rainfall: pd.Series | None, prior_values: dict,
                     soil_wetness: pd.Series | None = None) -> SkillResult:
    """Relate each year's change in storage to the rain that fell while it changed.

    The change between two calendar-year means is set against rainfall accumulated over
    those same two years. The fitted line gives two readable numbers: how much storage
    responds to a wetter or drier spell, and how much it changes in a spell of average
    rainfall. A fall at average rainfall means rainfall alone does not account for the
    decline; it does not say what does. This is a description: the interval assumes
    year-to-year independence and is not a calibrated test.
    """
    name = "storage_rainfall"
    if rainfall is None:
        return refuse(name, "no rainfall record was supplied", "supply rainfall for the same region")
    if rainfall.attrs.get("variable") != "precipitation":
        return refuse(name, "the second record is not precipitation", "supply a precipitation record")
    converted = weather_monthly(rainfall)
    if not converted.ok:
        return refuse(name, converted.refusal.failed, converted.refusal.would_change)
    rain = converted.series
    accumulated = rolling_accumulation(rain, 24)
    if not accumulated.ok:
        return refuse(name, accumulated.refusal.failed, accumulated.refusal.would_change)
    two_year = accumulated.series[accumulated.series.index.month == 12].dropna()
    two_year.index = two_year.index.year
    change = annual.diff().dropna()
    change.index = change.index.year
    years = change.index.intersection(two_year.index)
    if len(years) < MIN_PAIRS:
        return refuse(name, f"only {len(years)} years have both a storage change and two full years of rainfall",
                      "use longer records")
    dy, rain2 = change.loc[years].to_numpy(dtype=float), two_year.loc[years].to_numpy(dtype=float) / 2  # mm per year
    centred = (rain2 - rain2.mean()) / 100.0  # per 100 mm of yearly rainfall above the period average
    fit = sm.OLS(dy, sm.add_constant(centred)).fit()
    (a_low, a_high), (b_low, b_high) = fit.conf_int(alpha=0.05)
    a, b = float(fit.params[0]), float(fit.params[1])
    r = float(np.corrcoef(centred, dy)[0, 1])
    yearly_rain = rain.groupby(rain.index.year).sum(min_count=12).dropna()
    yearly_rain.index = pd.to_datetime(yearly_rain.index.astype(str), format="%Y")
    rain_slope, rain_test = sens_slope(yearly_rain), mann_kendall_prewhitened(yearly_rain)
    rain_trend = None
    if rain_slope.ok and rain_test.ok:
        rain_trend = {"sen_slope_mm_per_year_per_year": rain_slope.values["slope"],
                      "interval": [rain_slope.values["ci_low"], rain_slope.values["ci_high"]],
                      "trend_detected": bool(rain_test.values["trend_detected"]), "direction": rain_test.values["direction"],
                      "mean_mm_per_year": float(yearly_rain.mean()), "first_year": int(yearly_rain.index[0].year),
                      "last_year": int(yearly_rain.index[-1].year)}
    soil = None
    if soil_wetness is not None and soil_wetness.attrs.get("variable") == "soil_wetness":
        yearly_soil = soil_wetness.groupby(soil_wetness.index.year).mean()
        yearly_soil = yearly_soil[soil_wetness.groupby(soil_wetness.index.year).count() == 12]
        yearly_soil.index = pd.to_datetime(yearly_soil.index.astype(str), format="%Y")
        s_slope, s_test = sens_slope(yearly_soil), mann_kendall_prewhitened(yearly_soil)
        if s_slope.ok and s_test.ok:
            soil = {"sen_slope_per_decade": 10 * s_slope.values["slope"], "trend_detected": bool(s_test.values["trend_detected"]),
                    "direction": s_test.values["direction"], "mean": float(yearly_soil.mean()),
                    "product": soil_wetness.attrs.get("product"),
                    "note": "modelled wetness as a fraction of saturation; it cannot be subtracted from storage in cm"}
    responds = b_low > 0
    trend_found = bool(prior_values["conclusion"]["evidence"].get("detected"))
    if a_high < 0 or a_low > 0:
        link = "falls_at_average_rainfall" if a_high < 0 else "rises_at_average_rainfall"
        verb = "fell" if a_high < 0 else "rose"
        near, far = sorted([abs(a_low), abs(a_high)])
        size = f"about {abs(a):.1f} cm a year (range {near:.1f} to {far:.1f})"
        if trend_found:
            sentence = (f"In a spell of average rainfall, storage still {verb} by {size}, so rainfall alone "
                        f"does not account for the {'decline' if verb == 'fell' else 'rise'}.")
        else:
            sentence = (f"Once rainfall is taken into account, the record points to storage that {verb} by {size} "
                        "in a spell of average rainfall; that reading is a description, not a tested result.")
    elif responds:
        link = "follows_rainfall"
        sentence = "Year-to-year changes follow rainfall, and in a spell of average rainfall storage holds roughly level."
    else:
        link = "no_clear_link"
        sentence = "Year-to-year changes in storage show no clear link to rainfall in this record."
    if responds and link in ("falls_at_average_rainfall", "rises_at_average_rainfall"):
        sentence += f" Wetter spells do help: each extra 100 mm of yearly rain goes with about {b:.1f} cm more storage."
    if rain_trend is not None:
        sentence += (" Rainfall itself shows no detectable trend over the period." if not rain_trend["trend_detected"]
                     else f" Rainfall itself has been {rain_trend['direction']} over the period.")
    prior = prior_values["conclusion"]
    return SkillResult(name, plain({
        "n_years": len(years), "years": years.tolist(), "storage_change_at_average_rainfall_cm_per_year": a,
        "interval_at_average_rainfall": [a_low, a_high], "response_cm_per_100mm": b, "response_interval": [b_low, b_high],
        "correlation": r, "responds_to_rainfall": bool(responds), "link": link,
        "average_rainfall_mm_per_year": float(rain2.mean()), "rainfall_trend": rain_trend, "soil_wetness": soil,
        "pairs": [{"year": int(y), "storage_change_cm": float(d), "rainfall_mm_per_year": float(p)} for y, d, p in zip(years, dy, rain2)],
        "method": "ordinary least squares of yearly storage change on two-year rainfall; descriptive interval",
        "rainfall_product": rain.attrs.get("product"),
        "conclusion": {**prior, "statement": f"{prior['statement']} {sentence}",
                       "evidence": {**prior["evidence"], "rainfall_link": link}}}))
