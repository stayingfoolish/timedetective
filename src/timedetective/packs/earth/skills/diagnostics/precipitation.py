"""Daily precipitation spells and window-defined wet-season timing."""

import numpy as np
import pandas as pd

from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse
from .weather import weather_audit, weather_extremes


@register("weather_precip_totals")
def weather_precip_totals(x: pd.Series) -> SkillResult:
    """Observed monthly/annual totals with coverage; no baseline or significance needed."""
    name = "weather_precip_totals"
    audit = weather_audit(x)
    if not audit.ok:
        return refuse(name, audit.refusal.failed, audit.refusal.would_change)
    if x.attrs.get("cadence") != "monthly" or x.attrs.get("units") != "mm/month" or x.attrs.get("variable") != "precipitation":
        return refuse(name, "normalized monthly precipitation required", "run weather_monthly")
    monthly = [{"month": str(d.date()), "total_mm": None if pd.isna(v) else float(v),
                "complete": not pd.isna(v)} for d,v in x.items()]
    annual = []
    for year, group in x.groupby(x.index.year):
        complete = len(group) == 12 and not group.isna().any()
        annual.append({"year": int(year), "total_mm": float(group.sum()) if complete else None,
                       "complete_months": int(group.notna().sum())})
    return SkillResult(name, {"monthly_totals": monthly, "annual_totals": annual,
        "interpretation": "Observed totals at the recorded grid support; incomplete totals are null, not zero.",
        "method_sources": ["precipitation_policy_v2"]})


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive bounds of true runs, with no calendar-year reset."""
    padded = np.r_[False, np.asarray(mask, dtype=bool), False].astype(int)
    return [(int(a), int(b)) for a, b in zip(np.flatnonzero(np.diff(padded) == 1),
                                            np.flatnonzero(np.diff(padded) == -1)-1)]


@register("weather_precip_spells")
def weather_precip_spells(x: pd.Series, *, analyses: list[str], wet_threshold: float) -> SkillResult:
    """Full-record spell catalogue; boundary/missing-data censoring is explicit, not zero rain."""
    name = "weather_precip_spells"
    if "extremes" not in analyses:
        return SkillResult(name, {"status": "not_requested"})
    result = weather_extremes(x, wet_threshold)
    if not result.ok:
        return refuse(name, result.refusal.failed, result.refusal.would_change)
    values = dict(result.values)
    for row in values["annual_indices"]:
        group = x[x.index.year == row["year"]]
        row.update(r10mm_days=int((group >= 10).sum()), r20mm_days=int((group >= 20).sum()))
    catalogue = []
    data = x.to_numpy()
    valid = np.isfinite(data)
    for kind, mask in [("dry", valid & (data < wet_threshold)), ("wet", valid & (data >= wet_threshold))]:
        for a, b in runs(mask):
            catalogue.append({"kind": kind, "start": str(x.index[a].date()), "end": str(x.index[b].date()),
                "days": int(b-a+1), "total_mm": float(data[a:b+1].sum()),
                "left_censored": bool(a == 0 or not valid[a-1]),
                "right_censored": bool(b == len(x)-1 or not valid[b+1])})
    values.update(spells=catalogue, method_sources=["zhang_2011", "precipitation_policy_v2"],
        scope="Annual indices plus cross-year spell catalogue. Censored run lengths are lower bounds, not completed durations.")
    return SkillResult(name, values)


@register("weather_precip_timing")
def weather_precip_timing(x: pd.Series, *, analyses: list[str], baseline: list[int],
                         windows: dict[str, list[str]] | None) -> SkillResult:
    """Dunning et al. (2016) stage-2 cumulative-anomaly timing in user-defined broad windows.

    Not the paper's full harmonic/automatic season classification or agronomic onset.
    Cross-year windows are identified by their starting year. No significance test.
    """
    name = "weather_precip_timing"
    if "timing" not in analyses:
        return SkillResult(name, {"status": "not_requested"})
    audit = weather_audit(x, "extremes")
    if not audit.ok:
        return refuse(name, audit.refusal.failed, audit.refusal.would_change)
    if not windows:
        return refuse(name, "wet-season search windows missing", "declare broad MM-DD start/end windows enclosing each season")
    expected = pd.date_range(f"{baseline[0]}-01-01", f"{baseline[1]}-12-31", freq="D")
    base = x.reindex(expected)
    if baseline[1]-baseline[0]+1 < 15 or base.isna().any():
        return refuse(name, "timing needs at least 15 complete baseline years", "supply complete baseline daily precipitation")
    mean = float(base.mean())
    if mean <= 0:
        return refuse(name, "zero-rain climatology has no wet season", "use a location with a measurable seasonal cycle")
    rows, failures = [], []
    for label, (begin, finish) in windows.items():
        for year in sorted(set(x.index.year)):
            try:
                start = pd.Timestamp(f"{year}-{begin}")
                end = pd.Timestamp(f"{year + int(finish < begin)}-{finish}")
                dates = pd.date_range(start, end, freq="D")
                group = x.reindex(dates)
                if len(group) < 30 or group.isna().any():
                    raise ValueError("search window incomplete or shorter than 30 days")
                cumulative = np.r_[0., np.cumsum(group.to_numpy()-mean)]
                minimum = int(np.argmin(cumulative))
                if minimum >= len(group):
                    raise ValueError("no wet-season rise within search window")
                maximum = minimum + int(np.argmax(cumulative[minimum:]))
                if minimum == 0 or maximum == len(group) or maximum <= minimum:
                    raise ValueError("season not enclosed by search window (boundary-censored or absent)")
                rows.append({"window": label, "year": int(year), "onset": str(dates[minimum].date()),
                    "cessation": str(dates[maximum-1].date()), "duration_days": maximum-minimum,
                    "rain_mm": float(group.iloc[minimum:maximum].sum()),
                    "cumulative_anomaly_gain_mm": float(cumulative[maximum]-cumulative[minimum])})
            except ValueError as exc:
                failures.append({"procedure": name, "failed": f"{label}/{year}: {exc}",
                    "would_change": "supply a complete, independently chosen broad window enclosing the season; do not optimize windows to get desired dates"})
    return SkillResult(name, {"timing": rows, "baseline_daily_mean_mm": mean,
        "subprocedure_refusals": failures, "windows": windows,
        "interpretation": "Cumulative-anomaly timing conditional on explicit windows; not planting advice or proof that onset changed.",
        "method_sources": ["dunning_2016", "precipitation_policy_v2"]})
