"""Stationary GEV annual-maximum return levels, conditional on explicit model assumptions."""

import warnings

import numpy as np
import pandas as pd
from scipy import stats

from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse
from .weather import weather_extremes


@register("weather_precip_return_levels")
def weather_precip_return_levels(x: pd.Series, *, analyses: list[str], return_periods: list[float],
                                seed: int, fit_resamples: int) -> SkillResult:
    """Fit SciPy GEV to complete annual Rx1day; refit parametric bootstrap intervals/KS.

    Stationarity and independence are assumptions, not established by non-rejection.
    Thirty years and extrapolation <= twice record length are conservative house rules.
    """
    name = "weather_precip_return_levels"
    if "return_levels" not in analyses:
        return SkillResult(name, {"status": "not_requested"})
    indices = weather_extremes(x)
    if not indices.ok:
        return refuse(name, indices.refusal.failed, indices.refusal.would_change)
    rows = indices.values["annual_indices"]
    y = np.array([r["rx1day_mm"] for r in rows])
    if len(y) < 30 or indices.values["excluded_years"] or np.ptp(y) <= 0:
        return refuse(name, "GEV requires at least 30 consecutive complete nonconstant annual maxima", "supply a longer homogeneous daily record; no extrapolation from a short sample")
    if not return_periods or any(not np.isfinite(t) or t <= 1 or t > 2*len(y) for t in return_periods) or not 99 <= fit_resamples <= 999:
        return refuse(name, "invalid return periods or bootstrap count", "use 1 < T <= twice record length and 99..999 resamples")
    rng = np.random.default_rng(seed)
    samples = []
    diagnostics = []
    failed = 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        params = stats.genextreme.fit(y)
        levels = stats.genextreme.isf(1 / np.array(return_periods), *params)
        observed = float(stats.kstest(y, "genextreme", args=params).statistic)
        for _ in range(fit_resamples):
            sample = stats.genextreme.rvs(*params, size=len(y), random_state=rng)
            try:
                fitted = stats.genextreme.fit(sample)
                values = stats.genextreme.isf(1 / np.array(return_periods), *fitted)
                if not np.isfinite(values).all() or fitted[2] <= 0:
                    raise ValueError("invalid fit")
                samples.append(values)
                diagnostics.append(float(stats.kstest(sample, "genextreme", args=fitted).statistic))
            except (ValueError, FloatingPointError):
                failed += 1
    if not np.isfinite(levels).all() or params[2] <= 0 or failed:
        return refuse(name, f"GEV fit/bootstrap unstable ({failed} failed resamples)", "review annual maxima and fitting method; do not hide failed fits")
    gof_p = float((1+np.count_nonzero(np.array(diagnostics) >= observed))/(fit_resamples+1))
    if gof_p < .01:
        return refuse(name, "stationary GEV distribution failed refitted KS screen at .01", "validate an alternative extreme-value model")
    intervals = np.quantile(samples, [.025, .975], axis=0)
    rho = float(np.corrcoef(y[:-1], y[1:])[0, 1])
    return SkillResult(name, {"annual_maxima": rows, "n_years": len(y),
        "parameters": {"scipy_c": float(params[0]), "xi": float(-params[0]), "location": float(params[1]), "scale": float(params[2])},
        "return_levels": [{"years": t, "daily_mm": float(v), "conditional_95_interval": [float(lo), float(hi)]}
                          for t, v, lo, hi in zip(return_periods, levels, *intervals)],
        "refitted_ks_p": gof_p, "annual_lag1": rho, "fit_resamples": fit_resamples, "seed": seed,
        "inference_status": "conditional_model_estimates_not_calibrated",
        "limitations": "Assumes stationary independent annual maxima and a GEV tail. Fit non-rejection is not proof. Gridded daily values are not gauge design storms, subdaily IDF, or flood return periods. Intervals condition on this model and exclude measurement/model-choice uncertainty.",
        "method_sources": ["scipy_genextreme", "scipy_gof", "zhang_2011", "precipitation_policy_v2"]})
