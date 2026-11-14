"""Do drifting series share a long-run balance?"""

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint
from statsmodels.tsa.vector_ar.vecm import coint_johansen

from timedetective.skills.checks import guard
from timedetective.skills.registry import register
from timedetective.skills.relationship.align import guard_pair
from timedetective.skills.result import SkillResult, refuse


@register("cointegration_engle_granger")
def cointegration_engle_granger(x: pd.Series, y: pd.Series, alpha: float = 0.05) -> SkillResult:
    """Engle-Granger test: the null is no cointegration between two series.

    Assumes both series are non-stationary (unit root); on stationary series the
    result is meaningless. Two aligned, regular, gap-free series.
    """
    name = "cointegration_engle_granger"
    if (r := guard_pair(name, x, y, 40)) is not None:
        return r
    stat, p, _ = coint(y.to_numpy(dtype=float), x.to_numpy(dtype=float))
    return SkillResult(name, {"cointegrated": bool(p < alpha), "statistic": float(stat), "p_value": float(p), "alpha": alpha})


@register("johansen")
def johansen(frame: pd.DataFrame, det_order: int = -1, k_ar_diff: int = 1) -> SkillResult:
    """Johansen trace test: the number of cointegrating relations among several series, at 5%.

    Assumes every column is non-stationary and the system is a linear VAR;
    columns share one regular, gap-free index. `det_order` must match the data:
    -1 (default) for series without drift, 0 or 1 when they drift; a constant
    fitted to driftless series makes the test over-reject (measured in
    tests/skills/relationship). A full rank means the series look stationary,
    which contradicts the assumption, so it is reported as `full_rank` and not
    as cointegration.
    """
    name = "johansen"
    if not isinstance(frame, pd.DataFrame) or frame.shape[1] < 2:
        return refuse(name, "input must be a DataFrame with two or more columns", "pass the series as columns of one DataFrame")
    for col in frame.columns:
        if (r := guard(name, frame[col], 20 * frame.shape[1])) is not None:
            return r
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = coint_johansen(frame.to_numpy(dtype=float), det_order, k_ar_diff)
    trace, crit = res.lr1, res.cvt[:, 1]
    rank = 0
    for stat, c in zip(trace, crit):
        if stat <= c:
            break
        rank += 1
    return SkillResult(name, {
        "cointegration_rank": rank,
        "cointegrated": 0 < rank < frame.shape[1],
        "full_rank": rank == frame.shape[1],
        "det_order": det_order,
        "trace_statistics": np.asarray(trace).tolist(),
        "critical_values_5pct": np.asarray(crit).tolist(),
        "n_series": frame.shape[1],
    })
