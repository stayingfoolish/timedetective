"""Cross-product checks keep lineage and spatial-support limitations visible."""

import pandas as pd

from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse
from timedetective.packs.earth.skills.transforms.monthly import weather_monthly
from timedetective.packs.earth.skills.trend.seasonal import weather_seasons


@register("weather_compare")
def weather_compare(x: pd.Series, companion: pd.Series | None, seasons: dict,
                    baseline_start: int, baseline_end: int, event_start: int, event_end: int) -> SkillResult:
    """Compare anomalies on the same dates, units, and requested support; no independence assumption."""
    name = "weather_compare"
    if companion is None:
        return refuse(name, "no comparison record", "supply a second product and its provenance")
    if x.attrs.get("variable") != companion.attrs.get("variable"):
        return refuse(name, "different variables", "supply a comparison measuring the same quantity")
    if x.attrs.get("spatial_support") != companion.attrs.get("spatial_support"):
        return refuse(name, "different requested spatial supports", "aggregate to a common polygon or specify the same point")
    a, b = weather_monthly(x), weather_monthly(companion)
    for result in (a, b):
        if not result.ok:
            return refuse(name, result.refusal.failed, result.refusal.would_change)
    if a.series.attrs["units"] != b.series.attrs["units"] or x.attrs["time_standard"] != companion.attrs["time_standard"]:
        return refuse(name, "unit or time-standard mismatch", "harmonize units and accumulation boundaries")
    args = dict(seasons=seasons, baseline_start=baseline_start, baseline_end=baseline_end,
                event_start=event_start, event_end=event_end)
    aa, bb = weather_seasons(a.series, **args), weather_seasons(b.series, **args)
    for result in (aa, bb):
        if not result.ok:
            return refuse(name, result.refusal.failed, result.refusal.would_change)
    checks = {}
    for label in seasons:
        left, right = aa.values["seasons"][label], bb.values["seasons"][label]
        checks[label] = {"primary_event_anomaly": left["event_mean_anomaly"],
            "companion_event_anomaly": right["event_mean_anomaly"],
            "same_anomaly_sign": bool(left["event_mean_anomaly"] * right["event_mean_anomaly"] > 0),
            "primary_below_threshold_count": left["event_below_threshold_count"],
            "companion_below_threshold_count": right["event_below_threshold_count"]}
    same_lineage = bool(set(x.attrs.get("lineage", [])) & set(companion.attrs.get("lineage", [])))
    return SkillResult(name, {"comparison": checks, "shared_lineage_declared": same_lineage,
        "independence_established": False, "primary_product": x.attrs["product"],
        "companion_product": companion.attrs["product"],
        "primary_resolution": x.attrs.get("spatial_resolution", "unknown"),
        "companion_resolution": companion.attrs.get("spatial_resolution", "unknown"),
        "limitations": "point products sample different grid footprints; common point is not matched area support; agreement cannot by itself upgrade claim strength"})
