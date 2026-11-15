"""Weather data contracts and daily precipitation summaries."""

from datetime import date
import json

import numpy as np
import pandas as pd

from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("weather_audit")
def weather_audit(x: pd.Series, intent: str = "seasonal") -> SkillResult:
    """Validate metadata, calendar, physical units and finite values; never impute."""
    name = "weather_audit"
    required = {"units", "cadence", "source", "retrieved", "variable", "product",
                "version", "spatial_support", "quality", "sha256", "time_standard"}
    missing = required - x.attrs.keys()
    if missing:
        return refuse(name, f"missing metadata: {sorted(missing)}", "provide a provenance sidecar")
    try:
        json.dumps(x.attrs, allow_nan=False)
    except (TypeError, ValueError):
        return refuse(name, "metadata are not finite JSON values", "use quoted ISO dates and JSON-compatible finite metadata")
    if any(not isinstance(x.attrs[k], str) or not x.attrs[k].strip() for k in required - {"spatial_support"}):
        return refuse(name, "empty or non-text provenance fields", "supply explicit nonempty provenance fields")
    if not isinstance(x.attrs["spatial_support"], dict) or not x.attrs["spatial_support"].get("kind"):
        return refuse(name, "invalid spatial support", "declare point, polygon or other explicit spatial support")
    try:
        date.fromisoformat(x.attrs["retrieved"])
    except (ValueError, TypeError):
        return refuse(name, "invalid retrieval date", "use an ISO date")
    if intent not in {"seasonal", "trend", "discovery", "extremes", "weather"}:
        return refuse(name, f"unsupported intent: {intent}",
                      "use a supported descriptive analysis; attribution, forecasting, SPI and return periods need separate validated methods")
    if not isinstance(x.index, pd.DatetimeIndex) or len(x) < 2 or x.index.hasnans:
        return refuse(name, "need dated observations", "supply at least two valid dates")
    if x.index.has_duplicates or not x.index.is_monotonic_increasing or x.index.tz is not None:
        return refuse(name, "duplicate, unsorted or timezone-aware dates", "supply unique ordered dates with a declared time standard")
    if not x.index.equals(x.index.normalize()):
        return refuse(name, "daily/monthly dates are not normalized", "supply midnight date labels and the original accumulation time standard")
    if x.attrs["cadence"] not in {"daily", "monthly"}:
        return refuse(name, "unsupported cadence", "provide daily totals/means or monthly totals/means")
    expected = pd.date_range(x.index[0], x.index[-1], freq="D" if x.attrs["cadence"] == "daily" else "MS")
    if x.attrs["cadence"] == "monthly" and not (x.index.is_month_start).all():
        return refuse(name, "monthly timestamps must be month-start", "normalize dates without changing their calendar month")
    if not x.index.equals(expected):
        return refuse(name, "irregular or absent timestamps", "include every calendar timestamp and represent missing observations explicitly as NaN")
    try:
        y = x.to_numpy(dtype=float)
    except (ValueError, TypeError):
        return refuse(name, "non-numeric observations", "supply numeric values and NaN for missing")
    if np.isinf(y).any():
        return refuse(name, "infinite observations", "correct invalid values upstream")
    variable, unit = x.attrs["variable"], x.attrs["units"]
    allowed = {"precipitation": {"mm/day", "mm/month", "mm"}, "temperature": {"C", "K"},
               "wind_speed": {"m/s"}, "relative_humidity": {"%"}, "surface_pressure": {"kPa", "hPa"}}
    if variable not in allowed or unit not in allowed[variable]:
        return refuse(name, f"unsupported variable/unit: {variable}/{unit}", "supply a documented conversion")
    if variable == "precipitation" and ((x.attrs["cadence"] == "daily" and unit == "mm/month") or
                                          (x.attrs["cadence"] == "monthly" and unit == "mm")):
        return refuse(name, "ambiguous precipitation accumulation interval", "use mm/day for rates or mm/month for monthly totals")
    finite = y[np.isfinite(y)]
    if not len(finite) or (variable in {"precipitation", "wind_speed", "surface_pressure", "relative_humidity"} and (finite < 0).any()):
        return refuse(name, "empty record or physically invalid negative values", "apply documented fill values and quality flags")
    if variable == "relative_humidity" and (finite > 100).any():
        return refuse(name, "relative humidity above 100 percent", "review units and quality flags")
    if intent == "extremes" and (variable != "precipitation" or x.attrs["cadence"] != "daily"):
        return refuse(name, "daily precipitation required for rainfall extremes", "provide daily precipitation; monthly averages cannot recover extremes")
    return SkillResult(name, {"n": len(x), "missing": int(np.isnan(y).sum()),
        "start": str(x.index[0].date()), "end": str(x.index[-1].date()),
        "variable": variable, "units": unit, "intent": intent,
        "spatial_support": x.attrs["spatial_support"], "quality": x.attrs["quality"],
        "known_issues": x.attrs.get("known_issues", []), "metadata_review": "not a homogeneity certification"})


@register("weather_extremes")
def weather_extremes(x: pd.Series, wet_threshold: float = 1.0) -> SkillResult:
    """ETCCDI-style Rx1day/Rx5day/wet-day counts, with strict complete-year support.

    Zhang et al. (2011), doi:10.1002/wcc.147. CDD below is explicitly within-year,
    not the cross-year ETCCDI spell convention. No return-period inference.
    """
    name = "weather_extremes"
    if x.attrs.get("variable") != "precipitation" or x.attrs.get("cadence") != "daily":
        return refuse(name, "not daily precipitation", "supply daily precipitation for extremes")
    check = weather_audit(x, "extremes")
    if not check.ok:
        return refuse(name, check.refusal.failed, check.refusal.would_change)
    if wet_threshold <= 0:
        return refuse(name, "wet threshold must be positive", "specify a positive threshold in mm/day")
    rows, excluded = [], []
    for year, group in x.groupby(x.index.year):
        expected = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
        if not group.index.equals(expected) or group.isna().any():
            excluded.append(int(year))
            continue
        dry = group.to_numpy() < wet_threshold
        longest = current = 0
        for flag in dry:
            current = current + 1 if flag else 0
            longest = max(longest, current)
        wet = group >= wet_threshold
        rows.append({"year": int(year), "rx1day_mm": float(group.max()),
            "rx5day_within_year_mm": float(group.rolling(5).sum().max()),
            "wet_days": int(wet.sum()), "wet_day_total_mm": float(group[wet].sum()),
            "cdd_within_year_days": longest,
            "sdii_mm_per_wet_day": float(group[wet].mean()) if wet.any() else None})
    if not rows:
        return refuse(name, "no complete daily years", "supply complete years without filling missing rain with zero")
    return SkillResult(name, {"annual_indices": rows, "excluded_years": excluded,
        "wet_threshold_mm_per_day": wet_threshold,
        "scope": "within-year descriptive indices; gridded extremes are not station extremes; no flood or return-period claims"})
