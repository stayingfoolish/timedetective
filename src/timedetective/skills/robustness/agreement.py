"""Does a second method, or a second record, tell the same story?"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from timedetective.skills.checks import guard, time_axis
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult


def _both(x: pd.Series, alpha: float) -> dict:
    t, unit = time_axis(x)
    y = x.to_numpy(dtype=float)
    lags = int(np.floor(4 * (len(x) / 100) ** (2 / 9)))
    fit = sm.OLS(y, sm.add_constant(t)).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    ols_lo, ols_hi = fit.conf_int(alpha)[1]
    sen, _, sen_lo, sen_hi = stats.theilslopes(y, t, alpha=1 - alpha)
    return {
        "ols_slope": float(fit.params[1]), "ols_ci_low": float(ols_lo), "ols_ci_high": float(ols_hi),
        "sen_slope": float(sen), "sen_ci_low": float(sen_lo), "sen_ci_high": float(sen_hi),
        "slope_unit": f"per {unit}",
    }


@register("method_agreement")
def method_agreement(x: pd.Series, alpha: float = 0.05) -> SkillResult:
    """Compares the least-squares slope (Newey-West interval) with the Theil-Sen slope.

    `methods_agree` requires the same sign and each estimate inside the other's
    interval. Assumes a regular, gap-free series. Disagreement usually means
    outliers or a non-linear trend.
    """
    name = "method_agreement"
    if (r := guard(name, x, 20)) is not None:
        return r
    v = _both(x, alpha)
    same_sign = v["ols_slope"] * v["sen_slope"] > 0
    inside = v["sen_ci_low"] <= v["ols_slope"] <= v["sen_ci_high"] and v["ols_ci_low"] <= v["sen_slope"] <= v["ols_ci_high"]
    return SkillResult(name, {**v, "same_sign": bool(same_sign), "methods_agree": bool(same_sign and inside), "alpha": alpha})


@register("independent_record_check")
def independent_record_check(x: pd.Series, y: pd.Series, alpha: float = 0.05) -> SkillResult:
    """Compares the Theil-Sen trends of two records of the same quantity (e.g. satellite and station).

    `records_agree` requires the same sign and overlapping intervals. Each series
    is regular and gap-free; they need not share an index, but must be in the
    same units over comparable periods for the comparison to mean anything.
    """
    name = "independent_record_check"
    for s in (x, y):
        if (r := guard(name, s, 20)) is not None:
            return r
    a, b = _both(x, alpha), _both(y, alpha)
    same_sign = a["sen_slope"] * b["sen_slope"] > 0
    overlap = a["sen_ci_low"] <= b["sen_ci_high"] and b["sen_ci_low"] <= a["sen_ci_high"]
    return SkillResult(name, {
        "slope_first": a["sen_slope"], "ci_first": [a["sen_ci_low"], a["sen_ci_high"]],
        "slope_second": b["sen_slope"], "ci_second": [b["sen_ci_low"], b["sen_ci_high"]],
        "slope_unit": a["slope_unit"],
        "same_sign": bool(same_sign),
        "intervals_overlap": bool(overlap),
        "records_agree": bool(same_sign and overlap),
        "alpha": alpha,
    })
