"""ADF and KPSS run as a pair, because their null hypotheses are opposite."""

import warnings

import pandas as pd
from statsmodels.tsa.stattools import adfuller, kpss

from timedetective.skills.checks import guard
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("stationarity")
def stationarity(x: pd.Series, regression: str = "c", alpha: float = 0.05) -> SkillResult:
    """Classifies a series as stationary, unit_root, conflict or inconclusive.

    `regression="c"` tests stationarity around a level, `"ct"` around a linear
    trend. ADF's null is a unit root; KPSS's null is stationarity. KPSS p-values
    are bounded to [0.01, 0.1] by the lookup table. Assumes a regular, gap-free series.
    """
    name = "stationarity"
    if regression not in ("c", "ct"):
        return refuse(name, f"regression must be 'c' or 'ct', got {regression!r}", "pass 'c' or 'ct'")
    if (r := guard(name, x, 25)) is not None:
        return r
    v = x.to_numpy(dtype=float)
    adf_stat, adf_p, *_ = adfuller(v, regression=regression, autolag="AIC", result_object=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        kpss_stat, kpss_p, *_ = kpss(v, regression=regression, nlags="auto")
    adf_rejects, kpss_rejects = adf_p < alpha, kpss_p < alpha
    label = {
        (True, False): "stationary",
        (False, True): "unit_root",
        (True, True): "conflict",
        (False, False): "inconclusive",
    }[(adf_rejects, kpss_rejects)]
    return SkillResult(name, {
        "stationarity": label,
        "regression": regression,
        "adf_statistic": float(adf_stat),
        "adf_p": float(adf_p),
        "kpss_statistic": float(kpss_stat),
        "kpss_p": float(kpss_p),
        "tests_agree": label in ("stationary", "unit_root"),
    })
