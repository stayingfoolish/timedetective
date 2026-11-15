"""Annual water-storage values from a gappy monthly record."""

import numpy as np
import pandas as pd

from timedetective.packs.earth.skills.common import plain
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse
from timedetective.skills.transforms.deseasonalize import deseasonalize_harmonic
from timedetective.skills.transforms.regularize import regularize

MIN_MONTHS_PER_YEAR = 4  # a third of the year; see docs/story_playbooks.md for why not six
MIN_YEARS = 15


@register("storage_annual")
def storage_annual(x: pd.Series) -> SkillResult:
    """Remove the seasonal cycle with a method that tolerates gaps, then average by calendar year.

    A year needs at least four months of data. No month is filled in; years with fewer than
    twelve are listed so a reader can see which values rest on little data. Also reports how
    persistent the monthly departures are (lag-1 correlation of consecutive months after
    removing the seasonal cycle and a straight line); the critic uses it to decide whether
    the trend test is being used inside the range it was calibrated for.
    """
    name = "storage_annual"
    cleaned = deseasonalize_harmonic(x, 12)
    if not cleaned.ok:
        return refuse(name, cleaned.refusal.failed, cleaned.refusal.would_change)
    yearly = regularize(cleaned.series, "YS", min_count=MIN_MONTHS_PER_YEAR)
    if not yearly.ok:
        return refuse(name, yearly.refusal.failed, yearly.refusal.would_change)
    annual = yearly.series
    while len(annual) and not np.isfinite(annual.iloc[0]):
        annual = annual.iloc[1:]
    while len(annual) and not np.isfinite(annual.iloc[-1]):
        annual = annual.iloc[:-1]
    if annual.isna().any():
        missing = [int(t.year) for t in annual.index[annual.isna()]]
        return refuse(name, f"years with fewer than {MIN_MONTHS_PER_YEAR} months of data inside the record: {missing}",
                      "the trend test needs every year; use a record without year-long holes")
    if len(annual) < MIN_YEARS:
        return refuse(name, f"only {len(annual)} usable years; {MIN_YEARS} are needed", "use a longer record")
    monthly = cleaned.series
    t = (monthly.index - monthly.index[0]).days.to_numpy() / 365.25
    ok = np.isfinite(monthly.to_numpy(dtype=float))
    residual = monthly.to_numpy(dtype=float) - np.polyval(np.polyfit(t[ok], monthly.to_numpy(dtype=float)[ok], 1), t)
    pairs = ok[:-1] & ok[1:]
    r1 = float(np.corrcoef(residual[:-1][pairs], residual[1:][pairs])[0, 1]) if pairs.sum() >= 24 else None
    counts = x.groupby(x.index.year).count()
    annual.attrs = {**x.attrs, "cadence": "annual", "aggregation": "calendar-year mean of deseasonalized months"}
    annual.name = x.name
    return SkillResult(name, plain({
        "n_years": len(annual), "first_year": annual.index[0].year, "last_year": annual.index[-1].year,
        "min_months_per_year": MIN_MONTHS_PER_YEAR,
        "thin_years": {int(y): int(c) for y, c in counts.items() if c < 12 and annual.index[0].year <= y <= annual.index[-1].year},
        "monthly_lag1_autocorrelation": r1, "seasonal_cycle": "two harmonics fitted to available months",
        "gap_filling": "none",
        "annual": [{"year": int(t.year), "value": float(v)} for t, v in annual.items()]}), series=annual)
