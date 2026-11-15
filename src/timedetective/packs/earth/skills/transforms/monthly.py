"""Calendar-aware aggregation, with no gap filling or partial-period extrapolation."""

import pandas as pd

from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse
from timedetective.packs.earth.skills.diagnostics.weather import weather_audit


@register("weather_monthly")
def weather_monthly(x: pd.Series) -> SkillResult:
    """Integrate precipitation rates; day-weight other variables only at seasonal aggregation."""
    name = "weather_monthly"
    check = weather_audit(x)
    if not check.ok:
        return refuse(name, check.refusal.failed, check.refusal.would_change)
    rain = x.attrs["variable"] == "precipitation"
    if x.attrs["cadence"] == "daily":
        grouped = x.resample("MS")
        out = grouped.sum(min_count=1) if rain else grouped.mean()
        complete = grouped.count() == out.index.days_in_month
        out = out.where(complete)
        conversion = "sum daily precipitation" if rain else "mean daily values"
    else:
        out = x.copy()
        if rain and x.attrs["units"] == "mm/day":
            out = out * out.index.days_in_month
            conversion = "monthly mean daily rate times actual calendar days"
        else:
            conversion = "already monthly"
    if x.attrs["variable"] == "temperature" and x.attrs["units"] == "K":
        out = out - 273.15
        conversion += "; Kelvin minus 273.15"
    out.attrs = {**x.attrs, "cadence": "monthly",
                 "units": "mm/month" if rain else "C" if x.attrs["variable"] == "temperature" else x.attrs["units"]}
    return SkillResult(name, {"conversion": conversion, "units": out.attrs["units"],
        "incomplete_months": [str(t.date()) for t in out.index[out.isna()]],
        "n_months": len(out), "gap_filling": "none"}, series=out)
