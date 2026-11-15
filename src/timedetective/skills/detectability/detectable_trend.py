"""What size of trend this record is able to show, and how long a record a given trend needs.

Both rest on the standard error of a least-squares slope under AR(1) noise.
For N equally spaced points over a span T with noise SD s and lag-1
autocorrelation phi:

    se(slope) ~= s * sqrt(12 / (N * T^2)) * sqrt((1 + phi) / (1 - phi))

A trend is detectable at two-sided level alpha with the stated power when
|slope| >= (z_{1-alpha/2} + z_{power}) * se. With monthly data, alpha = 0.05
and power = 0.9 this reduces to the familiar "3.3 sigma" years-to-detect rule
used in the atmospheric trend literature. The approximation is checked by
simulation in tests/skills/detectability/.
"""

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import acf

from timedetective.skills.checks import guard, steps_per_unit, time_axis
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


def _noise(x: pd.Series) -> tuple[float, float]:
    """SD and lag-1 autocorrelation of the residuals from a straight line."""
    t, _ = time_axis(x)
    y = x.to_numpy(dtype=float)
    resid = y - np.polyval(np.polyfit(t, y, 1), t)
    return float(resid.std(ddof=2)), float(acf(resid, nlags=1, fft=False)[1])


def _z(alpha: float, power: float) -> float:
    return float(stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power))


@register("minimum_detectable_trend")
def minimum_detectable_trend(x: pd.Series, alpha: float = 0.05, power: float = 0.9) -> SkillResult:
    """Smallest linear trend this record could detect, given its length and noise.

    Assumes AR(1) noise around a linear trend on a regular, gap-free series, with
    0 <= phi < 1 (negative phi is treated as 0, which is conservative).
    """
    name = "minimum_detectable_trend"
    if (r := guard(name, x, 20)) is not None:
        return r
    sd, phi = _noise(x)
    phi_used = min(max(phi, 0.0), 0.99)
    t, unit = time_axis(x)
    span = float(t[-1] - t[0]) * len(x) / (len(x) - 1)
    se = sd * np.sqrt(12 / (len(x) * span**2)) * np.sqrt((1 + phi_used) / (1 - phi_used))
    return SkillResult(name, {
        "minimum_detectable_trend": float(_z(alpha, power) * se),
        "slope_unit": f"per {unit}",
        "slope_standard_error": float(se),
        "noise_sd": sd,
        "lag1_autocorrelation": phi,
        "span": span,
        "alpha": alpha,
        "power": power,
    })


@register("record_length_needed")
def record_length_needed(x: pd.Series, trend: float, alpha: float = 0.05, power: float = 0.9) -> SkillResult:
    """Record length needed to detect a trend of size `trend` (per year for a
    datetime index, else per step), given this record's noise and cadence.

    Same assumptions as `minimum_detectable_trend`. `long_enough` compares the
    needed length with the record in hand.
    """
    name = "record_length_needed"
    if trend == 0:
        return refuse(name, "trend is zero", "pass the non-zero trend size you want to be able to detect")
    if (r := guard(name, x, 20)) is not None:
        return r
    sd, phi = _noise(x)
    phi_used = min(max(phi, 0.0), 0.99)
    t, unit = time_axis(x)
    m = steps_per_unit(x)
    needed = (_z(alpha, power) * sd * np.sqrt(12 / m) * np.sqrt((1 + phi_used) / (1 - phi_used)) / abs(trend)) ** (2 / 3)
    span = float(t[-1] - t[0]) * len(x) / (len(x) - 1)
    return SkillResult(name, {
        "length_needed": float(needed),
        "length_unit": unit,
        "length_available": span,
        "long_enough": bool(span >= needed),
        "trend": trend,
        "noise_sd": sd,
        "lag1_autocorrelation": phi,
        "alpha": alpha,
        "power": power,
    })
