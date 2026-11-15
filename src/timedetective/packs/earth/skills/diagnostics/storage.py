"""Water-storage check: is the water stored in and under a region changing?

Information only. The record is a satellite gravity estimate for a region; it does
not give a water-table depth, name a cause, or say how long a supply will last.
"""

import numpy as np
import pandas as pd

from timedetective.packs.earth.skills.common import metadata_problem, plain
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse

MIN_YEARS = 15
KINDS = {
    "total_water_storage": "all water stored on and under the land: soil moisture, snow, lakes and rivers, and groundwater together",
    "groundwater": "groundwater, after modelled soil moisture, snow and surface water were subtracted",
}


@register("storage_audit")
def storage_audit(x: pd.Series, not_answered: list[str] | None = None) -> SkillResult:
    """Check provenance, what the series measures, region size and record length.

    The minimum region size is the provider's stated resolution, carried in the
    series metadata by the adapter (`resolution_units`, `min_resolution_units`).
    A region below it is refused: its number would mostly describe its neighbours.
    """
    name = "storage_audit"
    if (problem := metadata_problem(x, "water_storage_anomaly")) is not None:
        return refuse(name, *problem)
    kind = x.attrs.get("storage_kind")
    if kind not in KINDS:
        return refuse(name, "the series does not say whether it is total water storage or groundwater",
                      "declare storage_kind in the metadata; the two must not be confused")
    if x.attrs["cadence"] != "monthly" or not x.index.is_month_start.all():
        return refuse(name, "need a monthly series labelled at month start", "aggregate to months first")
    if not x.index.equals(pd.date_range(x.index[0], x.index[-1], freq="MS")):
        return refuse(name, "months are absent from the index", "include every month and mark missing ones as NaN")
    units, minimum = x.attrs.get("resolution_units"), x.attrs.get("min_resolution_units")
    if units is None or minimum is None:
        return refuse(name, "the region's size relative to the product's resolution is not stated",
                      "load the data through an adapter that records it")
    if units < minimum:
        return refuse(name, f"the region spans {units} resolution cells; the provider's stated resolution is about {minimum}",
                      "ask about a larger region; the satellites cannot separate an area this small from its surroundings")
    values = x.to_numpy(dtype=float)
    present = np.isfinite(values)
    years = (x.index[present][-1] - x.index[present][0]).days / 365.25 if present.sum() > 1 else 0.0
    if years < MIN_YEARS:
        return refuse(name, f"the record spans {years:.1f} years; {MIN_YEARS} are needed", "use a longer record")
    gaps, run, start = [], 0, None
    for stamp, ok in zip(x.index, present):
        if not ok:
            run, start = run + 1, start or stamp
        elif run:
            gaps.append((run, start))
            run, start = 0, None
    longest = max(gaps, default=(0, None))
    return SkillResult(name, plain({
        "storage_kind": kind, "measures": KINDS[kind], "units": x.attrs["units"], "product": x.attrs["product"],
        "start": x.index[present][0], "end": x.index[present][-1], "years": years,
        "n_months": int(present.sum()), "n_missing_months": int((~present).sum()),
        "longest_gap_months": longest[0], "longest_gap_start": longest[1],
        "region_resolution_cells": units, "provider_resolution_cells": minimum,
        "area_km2": x.attrs.get("area_km2"), "spatial_support": x.attrs["spatial_support"],
        "not_answered": list(not_answered or []), "provider_uncertainty": x.attrs.get("provider_uncertainty"), "known_issues": x.attrs.get("known_issues", [])}))
