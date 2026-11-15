"""Turn satellite composites into a monthly vegetation series, without filling gaps."""

import numpy as np
import pandas as pd

from timedetective.packs.earth.skills.common import metadata_problem, plain
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("season_series")
def season_series(x: pd.Series) -> SkillResult:
    """Monthly mean of the valid composites that start in each month; a month with none stays missing.

    Composites screened out by the adapter (cloud, too few good pixels) arrive as
    NaN and are ignored. Nothing is interpolated or smoothed.
    """
    name = "season_series"
    if (problem := metadata_problem(x, "vegetation_index")) is not None:
        return refuse(name, *problem)
    grouped = x.resample("MS")
    monthly, counts = grouped.mean(), grouped.count()
    if monthly.notna().sum() < 24:
        return refuse(name, "fewer than 24 months with a valid reading", "use a longer record or a wider area")
    monthly.attrs = {**x.attrs, "cadence": "monthly", "aggregation": "mean of valid composites starting in the month"}
    monthly.name = x.name
    missing = monthly.index[monthly.isna()]
    return SkillResult(name, plain({
        "n_months": len(monthly), "n_missing_months": len(missing),
        "missing_months": [str(t.date())[:7] for t in missing][:60],
        "typical_composites_per_month": float(np.median(counts[counts > 0])),
        "gap_filling": "none", "smoothing": "none"}), series=monthly)
