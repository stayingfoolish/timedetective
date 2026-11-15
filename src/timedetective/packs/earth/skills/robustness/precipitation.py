"""Family correction of declared tests; correction cannot repair invalid local p-values."""

import pandas as pd
from statsmodels.stats.multitest import multipletests

from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("weather_precip_family")
def weather_precip_family(x: pd.Series, *, trend: dict, period: dict, changepoint: dict,
                         alpha: float, planned_members: int | None = None) -> SkillResult:
    """Holm over all tested seasons/methods in this product, including failed members as p=1."""
    groups = [trend, period, changepoint]
    tests = [dict(t) for g in groups for t in g.get("tests", [])]
    failed = sum(len(g.get("subprocedure_refusals", [])) for g in groups)
    if planned_members is not None:
        # An entire procedure can refuse before emitting per-season subresults.
        # Its declared hypotheses still belong to the family.
        failed = max(failed, planned_members - len(tests))
    pvalues = [t["p_value"] for t in tests] + [1.] * failed
    if pvalues:
        adjusted = multipletests(pvalues, alpha=alpha, method="holm")[1]
        for test, p in zip(tests, adjusted):
            test["p_holm"] = float(p)
            test["nominal_reject"] = bool(p <= alpha)
    return SkillResult("weather_precip_family", {"tests": tests, "family_size": len(pvalues),
        "failed_members": failed, "correction": "Holm", "alpha": alpha,
        "interpretation": "Nominal decisions only; local bootstrap calibration is not implied. Product-family correction is also applied by the run coordinator.",
        "method_sources": ["statsmodels_multipletests", "wilks_2016", "precipitation_policy_v2"]})


@register("weather_precip_global")
def weather_precip_global(x: pd.Series, *, families: dict, alpha: float) -> SkillResult:
    """One declared family across every requested product, season and test, never best-product selection."""
    tests = []
    failed = 0
    for product, family in families.items():
        failed += family["failed_members"]
        tests.extend({**t, "product": product} for t in family["tests"])
    pvalues = [t["p_value"] for t in tests] + [1.] * failed
    if not tests:
        return refuse("weather_precip_global", "no supported statistical tests completed",
                      "request supported tests with sufficient complete observations; descriptive results remain separate")
    if pvalues:
        adjusted = multipletests(pvalues, alpha=alpha, method="holm")[1]
        for test, p in zip(tests, adjusted):
            test.pop("p_holm", None)
            test["p_holm_global"] = float(p)
            test["nominal_reject"] = bool(p <= alpha)
    return SkillResult("weather_precip_global", {"tests": tests, "family_size": len(pvalues),
        "failed_members": failed, "alpha": alpha, "correction": "Holm across products and all declared season/test combinations",
        "interpretation": "Experimental nominal decisions, not a certification of significance. Product agreement is not independent replication.",
        "method_sources": ["statsmodels_multipletests", "wilks_2016", "precipitation_policy_v2"]})
