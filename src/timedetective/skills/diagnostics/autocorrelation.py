"""Serial correlation of a series or of residuals."""

import pandas as pd
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import acf

from timedetective.skills.checks import guard
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult


@register("autocorrelation")
def autocorrelation(x: pd.Series, nlags: int | None = None, alpha: float = 0.05) -> SkillResult:
    """Lag-1 autocorrelation and a Ljung-Box test of no serial correlation.

    Assumes a regular, gap-free series with trend and season already removed;
    on a trending series the autocorrelation is inflated by the trend itself.
    """
    name = "autocorrelation"
    if (r := guard(name, x, 12)) is not None:
        return r
    nlags = nlags or min(10, len(x) // 5)
    rho = acf(x.to_numpy(dtype=float), nlags=nlags, fft=False)
    lb = acorr_ljungbox(x.to_numpy(dtype=float), lags=[nlags])
    p = float(lb["lb_pvalue"].iloc[0])
    return SkillResult(name, {
        "lag1_autocorrelation": float(rho[1]),
        "acf": rho.tolist(),
        "ljung_box_lags": nlags,
        "ljung_box_p": p,
        "autocorrelated": p < alpha,
    })
