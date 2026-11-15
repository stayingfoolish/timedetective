"""Record length, cadence and gaps."""

import numpy as np
import pandas as pd

from timedetective.skills.checks import cadence, guard, is_regular, time_axis
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult


@register("record_summary")
def record_summary(x: pd.Series) -> SkillResult:
    """Assumes nothing. Returns length, span, cadence, regularity and missing share."""
    name = "record_summary"
    if (r := guard(name, x, 1, allow_missing=True, need_regular=False, allow_constant=True)) is not None:
        return r
    t, unit = time_axis(x)
    n_missing = int(x.isna().sum())
    return SkillResult(name, {
        "n": len(x),
        "n_observed": len(x) - n_missing,
        "n_missing": n_missing,
        "missing_share": n_missing / len(x),
        "start": x.index[0],
        "end": x.index[-1],
        "span": float(t[-1] - t[0]),
        "span_unit": unit,
        "cadence": cadence(x.index),
        "regular": is_regular(x),
    })


@register("gap_audit")
def gap_audit(x: pd.Series) -> SkillResult:
    """Assumes a regular index with gaps stored as NaN. Returns the number and length of gaps."""
    name = "gap_audit"
    if (r := guard(name, x, 1, allow_missing=True, allow_constant=True)) is not None:
        return r
    missing = x.isna().to_numpy()
    edges = np.diff(np.concatenate([[0], missing.astype(int), [0]]))
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    lengths = ends - starts
    return SkillResult(name, {
        "n_gaps": len(starts),
        "longest_gap": int(lengths.max()) if len(lengths) else 0,
        "gap_starts": [x.index[i] for i in starts],
        "gap_lengths": lengths.tolist(),
        "has_gaps": bool(len(starts)),
    })
