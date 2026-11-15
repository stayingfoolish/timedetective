"""Were a fitted model's assumptions met? Run on residuals."""

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox, het_breuschpagan
from statsmodels.tools import add_constant

from timedetective.skills.checks import guard
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult


@register("residual_diagnostics")
def residual_diagnostics(residuals: pd.Series, alpha: float = 0.05) -> SkillResult:
    """Ljung-Box (serial correlation), Jarque-Bera (normality) and Breusch-Pagan against time (changing variance).

    Assumes regular, gap-free residuals from a model that has already been fitted.
    """
    name = "residual_diagnostics"
    if (r := guard(name, residuals, 20)) is not None:
        return r
    e = residuals.to_numpy(dtype=float)
    lags = min(10, len(e) // 5)
    lb_p = float(acorr_ljungbox(e, lags=[lags])["lb_pvalue"].iloc[0])
    jb_p = float(stats.jarque_bera(e).pvalue)
    bp_p = float(het_breuschpagan(e - e.mean(), add_constant(np.arange(len(e), dtype=float)))[1])
    return SkillResult(name, {
        "ljung_box_p": lb_p,
        "jarque_bera_p": jb_p,
        "breusch_pagan_p": bp_p,
        "residuals_uncorrelated": lb_p >= alpha,
        "residuals_normal": jb_p >= alpha,
        "variance_stable": bp_p >= alpha,
    })
