"""Is there a repeating cycle, and at what period?"""

from math import comb

import numpy as np
import pandas as pd
from scipy import signal, stats
from statsmodels.tsa.stattools import acf

from timedetective.skills.checks import guard, phase
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("seasonality_acf")
def seasonality_acf(x: pd.Series, max_period: int | None = None, alpha: float = 0.05) -> SkillResult:
    """Seasonal period from the highest local peak of the autocorrelation function.

    Assumes a regular, gap-free, detrended series with several full cycles.
    A peak counts only if it exceeds the white-noise bound z/sqrt(n), with z
    Bonferroni-adjusted for the number of lags searched.
    """
    name = "seasonality_acf"
    if (r := guard(name, x, 24)) is not None:
        return r
    n = len(x)
    max_period = max_period or n // 3
    rho = acf(x.to_numpy(dtype=float), nlags=max_period + 1, fft=False)
    peaks = [k for k in range(2, max_period + 1) if rho[k] > rho[k - 1] and rho[k] >= rho[k + 1]]
    bound = float(stats.norm.ppf(1 - alpha / (2 * (max_period - 1))) / np.sqrt(n))
    if not peaks:
        return SkillResult(name, {"seasonal": False, "period": None, "acf_at_period": None, "bound": bound})
    best = max(peaks, key=lambda k: rho[k])
    seasonal = bool(rho[best] > bound)
    return SkillResult(name, {
        "seasonal": seasonal,
        "period": int(best) if seasonal else None,
        "acf_at_period": float(rho[best]),
        "bound": float(bound),
    })


def _fisher_g_pvalue(g: float, m: int) -> float:
    """Exact p-value of Fisher's g for m periodogram ordinates (Fisher 1929).

    Terms are summed in log space; the alternating sum loses precision for
    large m, so the result is clipped to [0, 1].
    """
    total = 0.0
    for j in range(1, int(np.floor(1 / g)) + 1):
        term = comb(m, j) * (1 - j * g) ** (m - 1)
        total += term if j % 2 else -term
    return float(min(max(total, 0.0), 1.0))


@register("seasonality_periodogram")
def seasonality_periodogram(x: pd.Series, alpha: float = 0.05) -> SkillResult:
    """Dominant period from the periodogram, with Fisher's g-test that the peak is not noise.

    Assumes a regular, gap-free series; a linear trend is removed internally by
    the periodogram. A largest peak always exists, so `period` is reported only
    when the g-test rejects white noise.
    """
    name = "seasonality_periodogram"
    if (r := guard(name, x, 24)) is not None:
        return r
    freqs, power = signal.periodogram(x.to_numpy(dtype=float), detrend="linear")
    freqs, power = freqs[1:], power[1:]
    if len(x) % 2 == 0:  # drop the Nyquist ordinate, which has a different distribution
        freqs, power = freqs[:-1], power[:-1]
    if power.sum() == 0:
        return refuse(name, "no variance left after removing a linear trend", "nothing periodic to test")
    k = int(np.argmax(power))
    g = float(power[k] / power.sum())
    p = _fisher_g_pvalue(g, len(power))
    seasonal = p < alpha
    return SkillResult(name, {
        "seasonal": seasonal,
        "period": float(1 / freqs[k]) if seasonal else None,
        "peak_period": float(1 / freqs[k]),
        "fisher_g": g,
        "fisher_g_p": p,
    })


@register("seasonal_kruskal")
def seasonal_kruskal(x: pd.Series, period: int, alpha: float = 0.05) -> SkillResult:
    """Kruskal-Wallis test that the phases of the cycle (e.g. months) share one distribution.

    Assumes a regular, detrended series with at least two full cycles.
    """
    name = "seasonal_kruskal"
    if period < 2:
        return refuse(name, f"period must be at least 2, got {period}", "pass the seasonal period")
    if (r := guard(name, x, 2 * period)) is not None:
        return r
    ph = phase(x, period)
    groups = [x.to_numpy(dtype=float)[ph == k] for k in range(period)]
    stat, p = stats.kruskal(*[g for g in groups if len(g)])
    return SkillResult(name, {"kruskal_statistic": float(stat), "kruskal_p": float(p), "seasonal": bool(p < alpha), "period": period})
