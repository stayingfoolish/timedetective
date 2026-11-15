"""Smoothers that return an estimate of the slow-moving level. For looking, not for testing."""

import pandas as pd
from scipy.signal import savgol_filter
from statsmodels.nonparametric.smoothers_lowess import lowess
from statsmodels.tsa.filters.hp_filter import hpfilter

from timedetective.skills.checks import guard
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("moving_average")
def moving_average(x: pd.Series, window: int, center: bool = True) -> SkillResult:
    """Rolling mean over `window` steps. Assumes the window spans at least one seasonal cycle.

    The first and last half-window are NaN when centered: endpoints are not estimated.
    """
    name = "moving_average"
    if window < 2:
        return refuse(name, f"window must be at least 2, got {window}", "pass a longer window")
    if (r := guard(name, x, window + 1)) is not None:
        return r
    out = x.rolling(window, center=center).mean()
    if center and window % 2 == 0:  # 2 x m moving average keeps the estimate centered
        out = out.rolling(2).mean().shift(-1)
    return SkillResult(name, {"window": window, "centered": center}, series=out.rename(x.name))


@register("loess_trend")
def loess_trend(x: pd.Series, frac: float = 0.3) -> SkillResult:
    """LOWESS smooth using a fraction `frac` of the points for each local fit.

    Assumes a smooth underlying level. The span is a judgment call; the fit is weakest at the ends.
    """
    name = "loess_trend"
    if not 0 < frac <= 1:
        return refuse(name, f"frac must be in (0, 1], got {frac}", "pass a span between 0 and 1")
    if (r := guard(name, x, 10)) is not None:
        return r
    fitted = lowess(x.to_numpy(dtype=float), range(len(x)), frac=frac, return_sorted=False)
    return SkillResult(name, {"frac": frac}, series=pd.Series(fitted, index=x.index, name=x.name))


@register("hp_filter")
def hp_filter(x: pd.Series, lamb: float) -> SkillResult:
    """Hodrick-Prescott trend with smoothing parameter `lamb` (required, never defaulted).

    Assumes a smooth trend and a zero-mean cycle. Known to bias the endpoints and
    can create spurious cycles; use for comparison with economic practice only.
    """
    name = "hp_filter"
    if lamb <= 0:
        return refuse(name, f"lamb must be positive, got {lamb}", "pass a positive smoothing parameter")
    if (r := guard(name, x, 10)) is not None:
        return r
    _, trend = hpfilter(x.to_numpy(dtype=float), lamb=lamb)
    return SkillResult(name, {"lamb": lamb, "endpoint_bias_warning": True}, series=pd.Series(trend, index=x.index, name=x.name))


@register("savgol_smooth")
def savgol_smooth(x: pd.Series, window: int, polyorder: int = 2) -> SkillResult:
    """Savitzky-Golay filter: a local polynomial fit that smooths noise but keeps the height of peaks.

    Assumes a regular, gap-free series and noise that is short compared with
    `window`. Commonly used to clean cloud-affected vegetation index series.
    """
    name = "savgol_smooth"
    if window % 2 == 0 or window <= polyorder or polyorder < 1:
        return refuse(name, "window must be odd and larger than polyorder (>= 1)", "pass an odd window above the polynomial order")
    if (r := guard(name, x, window + 1)) is not None:
        return r
    smoothed = savgol_filter(x.to_numpy(dtype=float), window_length=window, polyorder=polyorder)
    return SkillResult(name, {"window": window, "polyorder": polyorder}, series=pd.Series(smoothed, index=x.index, name=x.name))
