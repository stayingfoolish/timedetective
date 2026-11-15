"""Model comparisons that separate a steady trend from a slope change or a single step."""

import numpy as np
import pandas as pd

from timedetective.skills.checks import guard, time_axis
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


def _ssr(design: np.ndarray, y: np.ndarray) -> float:
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    return float(((y - design @ beta) ** 2).sum())


def _bic(ssr: float, n: int, k: int) -> float:
    """Gaussian BIC up to a constant; k counts mean parameters, including a searched break location."""
    return n * np.log(ssr / n) + k * np.log(n)


@register("segmented_regression")
def segmented_regression(x: pd.Series, min_segment: int = 10) -> SkillResult:
    """Best single slope change in a continuous piecewise-linear trend, compared with one line by BIC.

    Assumes uncorrelated residuals. The break is found by search, so no p-value
    is reported; `delta_bic` (linear minus segmented, positive favours a slope
    change) counts the break location as a parameter.
    """
    name = "segmented_regression"
    if (r := guard(name, x, 2 * min_segment + 1)) is not None:
        return r
    t, unit = time_axis(x)
    y = x.to_numpy(dtype=float)
    n = len(y)
    ones = np.ones(n)
    linear_ssr = _ssr(np.column_stack([ones, t]), y)
    candidates = range(min_segment, n - min_segment)
    ssrs = [_ssr(np.column_stack([ones, t, np.clip(t - t[k], 0, None)]), y) for k in candidates]
    best = int(np.argmin(ssrs))
    k = candidates[best]
    beta, *_ = np.linalg.lstsq(np.column_stack([ones, t, np.clip(t - t[k], 0, None)]), y, rcond=None)
    return SkillResult(name, {
        "break_position": k,
        "break_time": x.index[k],
        "slope_before": float(beta[1]),
        "slope_after": float(beta[1] + beta[2]),
        "slope_unit": f"per {unit}",
        "bic_linear": _bic(linear_ssr, n, 2),
        "bic_segmented": _bic(ssrs[best], n, 4),
        "delta_bic": _bic(linear_ssr, n, 2) - _bic(ssrs[best], n, 4),
    })


@register("step_vs_trend")
def step_vs_trend(x: pd.Series, min_segment: int = 10) -> SkillResult:
    """Compares four descriptions by BIC: flat, one step, a linear trend, and a step plus a trend.

    Assumes uncorrelated residuals and at most one step. The step location is
    found by search and counted as a parameter. `best_model` is the lowest BIC;
    `bic_margin` is the gap to the runner-up.
    """
    name = "step_vs_trend"
    if (r := guard(name, x, 2 * min_segment + 1)) is not None:
        return r
    t, _ = time_axis(x)
    y = x.to_numpy(dtype=float)
    n = len(y)
    ones = np.ones(n)
    pos = np.arange(n)
    candidates = range(min_segment, n - min_segment + 1)
    if len(candidates) == 0:
        return refuse(name, "record too short for the minimum segment length", "use a longer record or a smaller min_segment")
    step_ssr = [_ssr(np.column_stack([ones, pos >= k]), y) for k in candidates]
    both_ssr = [_ssr(np.column_stack([ones, t, pos >= k]), y) for k in candidates]
    k_step, k_both = candidates[int(np.argmin(step_ssr))], candidates[int(np.argmin(both_ssr))]
    bic = {
        "flat": _bic(_ssr(ones[:, None], y), n, 1),
        "step": _bic(min(step_ssr), n, 3),
        "trend": _bic(_ssr(np.column_stack([ones, t]), y), n, 2),
        "step_and_trend": _bic(min(both_ssr), n, 4),
    }
    ranked = sorted(bic, key=bic.get)
    best = ranked[0]
    k = k_both if best == "step_and_trend" else k_step
    return SkillResult(name, {
        "best_model": best,
        "bic_margin": float(bic[ranked[1]] - bic[best]),
        "bic": {m: float(v) for m, v in bic.items()},
        "step_position": k,
        "step_time": x.index[k],
        "step_size": float(y[k:].mean() - y[:k].mean()),
    })
