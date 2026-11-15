"""Remove the seasonal cycle."""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.seasonal import MSTL, STL

from timedetective.skills.checks import guard, time_axis
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("deseasonalize_stl")
def deseasonalize_stl(x: pd.Series, period: int, robust: bool = True) -> SkillResult:
    """Series minus its STL seasonal component.

    Assumes a regular, gap-free, additive series with a known period and two or
    more full cycles. Estimates are less reliable at both ends of the record.
    """
    name = "deseasonalize_stl"
    if period < 2:
        return refuse(name, f"period must be at least 2, got {period}", "pass the seasonal period")
    if (r := guard(name, x, 2 * period + 1)) is not None:
        return r
    fit = STL(x.to_numpy(dtype=float), period=period, robust=robust).fit()
    out = pd.Series(x.to_numpy(dtype=float) - fit.seasonal, index=x.index, name=x.name)
    return SkillResult(name, {"period": period, "seasonal_amplitude": float(np.ptp(fit.seasonal)), "deseasonalized": True}, series=out)


@register("deseasonalize_mstl")
def deseasonalize_mstl(x: pd.Series, periods: list[int]) -> SkillResult:
    """Series minus all MSTL seasonal components, for data with several periods.

    Assumes a regular, gap-free, additive series covering two or more cycles of the longest period.
    """
    name = "deseasonalize_mstl"
    if not periods or min(periods) < 2:
        return refuse(name, "periods must be a non-empty list of integers of at least 2", "pass the seasonal periods")
    if (r := guard(name, x, 2 * max(periods) + 1)) is not None:
        return r
    fit = MSTL(x.to_numpy(dtype=float), periods=sorted(periods)).fit()
    seasonal = np.asarray(fit.seasonal).reshape(len(x), -1).sum(axis=1)
    out = pd.Series(x.to_numpy(dtype=float) - seasonal, index=x.index, name=x.name)
    return SkillResult(name, {"periods": sorted(periods), "deseasonalized": True}, series=out)


@register("deseasonalize_harmonic")
def deseasonalize_harmonic(x: pd.Series, period: float, n_harmonics: int = 2) -> SkillResult:
    """Series minus a fitted sum of sines and cosines (harmonic regression with a linear trend term).

    Assumes the seasonal amplitude and phase are fixed over the record. Tolerates
    gaps: the fit uses observed points only. `period` is in index steps.
    """
    name = "deseasonalize_harmonic"
    if period < 2 or n_harmonics < 1 or 2 * n_harmonics >= period:
        return refuse(name, "need period >= 2 and 1 <= n_harmonics < period / 2", "pass a valid period and harmonic count")
    if (r := guard(name, x, int(2 * period) + 2 * n_harmonics + 2, allow_missing=True)) is not None:
        return r
    steps = np.arange(len(x), dtype=float)
    t, _ = time_axis(x)
    harmonics = np.column_stack(
        [f(2 * np.pi * k * steps / period) for k in range(1, n_harmonics + 1) for f in (np.sin, np.cos)]
    )
    design = sm.add_constant(np.column_stack([t, harmonics]))
    obs = x.notna().to_numpy()
    fit = sm.OLS(x.to_numpy(dtype=float)[obs], design[obs]).fit()
    seasonal = harmonics @ fit.params[2:]
    out = pd.Series(x.to_numpy(dtype=float) - seasonal, index=x.index, name=x.name)
    return SkillResult(
        name,
        {"period": period, "n_harmonics": n_harmonics, "seasonal_amplitude": float(np.ptp(seasonal)), "deseasonalized": True},
        series=out,
    )
