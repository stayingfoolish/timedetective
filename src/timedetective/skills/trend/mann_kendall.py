"""The Mann-Kendall family, via pymannkendall."""

import warnings

import numpy as np
import pandas as pd
import pymannkendall as mk

from timedetective.skills.checks import guard, steps_per_unit, time_axis
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


def _values(x: pd.Series, res, alpha: float) -> dict:
    _, unit = time_axis(x)
    return {
        "direction": res.trend,  # "increasing", "decreasing" or "no trend"
        "trend_detected": bool(res.h),
        "p_value": float(res.p),
        "z": float(res.z),
        "tau": float(res.Tau),
        "s": float(res.s),
        "slope": float(res.slope) * steps_per_unit(x),
        "slope_unit": f"per {unit}",
        "alpha": alpha,
        "n": len(x),
    }


@register("mann_kendall")
def mann_kendall(x: pd.Series, alpha: float = 0.05) -> SkillResult:
    """Original Mann-Kendall test for a monotonic trend, with ties correction.

    Assumes serially independent observations; positive autocorrelation makes it
    reject too often. Assumes a regular, gap-free series.
    """
    name = "mann_kendall"
    if (r := guard(name, x, 10)) is not None:
        return r
    return SkillResult(name, _values(x, mk.original_test(x.to_numpy(dtype=float), alpha=alpha), alpha))


@register("mann_kendall_hamed_rao")
def mann_kendall_hamed_rao(x: pd.Series, alpha: float = 0.05) -> SkillResult:
    """Mann-Kendall with the Hamed-Rao variance correction for autocorrelated data.

    Assumes a regular, gap-free series; the correction uses the significant
    autocorrelations of the detrended ranks. Rejects less often than the
    original test under autocorrelation but still above 5% on trend-free AR(1)
    noise (see tests/calibration).
    """
    name = "mann_kendall_hamed_rao"
    if (r := guard(name, x, 20)) is not None:
        return r
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        res = mk.hamed_rao_modification_test(x.to_numpy(dtype=float), alpha=alpha)
    if not (np.isfinite(res.z) and np.isfinite(res.p)):
        return refuse(
            name,
            "the variance correction is negative for this series, so the statistic is undefined",
            "use `mann_kendall_tfpw` or `ols_trend_hac` instead",
        )
    return SkillResult(name, _values(x, res, alpha))


@register("mann_kendall_prewhitened")
def mann_kendall_prewhitened(x: pd.Series, alpha: float = 0.05) -> SkillResult:
    """Mann-Kendall on the series after removing lag-1 autocorrelation (plain prewhitening).

    Assumes AR(1) noise on a regular, gap-free series. Of the Mann-Kendall
    variants here it is the only one that holds a 5% false-positive rate on
    trend-free AR(1) noise (see tests/calibration); the price is lower power
    for weak trends, because prewhitening also removes part of the trend.
    """
    name = "mann_kendall_prewhitened"
    if (r := guard(name, x, 20)) is not None:
        return r
    res = mk.pre_whitening_modification_test(x.to_numpy(dtype=float), alpha=alpha)
    return SkillResult(name, _values(x, res, alpha))


@register("mann_kendall_tfpw")
def mann_kendall_tfpw(x: pd.Series, alpha: float = 0.05) -> SkillResult:
    """Mann-Kendall after trend-free prewhitening: remove the trend, remove lag-1
    autocorrelation, add the trend back, then test.

    Assumes AR(1) noise on a regular, gap-free series. Keeps more power than
    plain prewhitening but does not hold the 5% false-positive rate on
    trend-free AR(1) noise (see tests/calibration), so it cannot support a
    "significant" claim on its own.
    """
    name = "mann_kendall_tfpw"
    if (r := guard(name, x, 20)) is not None:
        return r
    res = mk.trend_free_pre_whitening_modification_test(x.to_numpy(dtype=float), alpha=alpha)
    return SkillResult(name, _values(x, res, alpha))


@register("seasonal_kendall")
def seasonal_kendall(x: pd.Series, period: int, alpha: float = 0.05) -> SkillResult:
    """Seasonal Mann-Kendall: tests each phase of the cycle separately and combines them.

    Assumes independence between years within a phase, and a regular, gap-free
    series that starts at the beginning of a cycle. The slope is per cycle
    (per year for monthly data with period 12).
    """
    name = "seasonal_kendall"
    if period < 2:
        return refuse(name, f"period must be at least 2, got {period}", "pass the seasonal period")
    if (r := guard(name, x, 4 * period)) is not None:
        return r
    res = mk.seasonal_test(x.to_numpy(dtype=float), period=period, alpha=alpha)
    values = _values(x, res, alpha)
    values.update(slope=float(res.slope), slope_unit="per cycle", period=period)
    return SkillResult(name, values)
