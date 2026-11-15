"""Descriptive seasonal events and competing models; no significance claims."""

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm

from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse
from timedetective.packs.earth.skills.diagnostics.weather import weather_audit


def seasonal_values(x: pd.Series, months: list[int]) -> pd.Series:
    """Year is the year containing the last month (DJF is Dec previous year–Feb)."""
    if not months or len(set(months)) != len(months) or any(m not in range(1, 13) for m in months):
        raise ValueError("season months must be unique integers in 1..12")
    if any(b != a % 12 + 1 for a, b in zip(months, months[1:])):
        raise ValueError("season months must be contiguous in calendar order")
    result = {}
    for year in range(x.index.year.min(), x.index.year.max() + 1):
        dates = [pd.Timestamp(year - int(m > months[-1]), m, 1) for m in months]
        values = x.reindex(dates)
        if values.isna().any():
            result[year] = np.nan
        elif x.attrs["variable"] == "precipitation":
            result[year] = float(values.sum())
        else:
            result[year] = float(np.average(values, weights=values.index.days_in_month))
    return pd.Series(result, dtype=float)


def model_evidence(s: pd.Series, event_start: int, event_end: int) -> dict:
    """Schwarz BIC on annual seasonal values; iid Gaussian ranking is exploratory.

    A searched step counts its position as a parameter; a prespecified episode
    has a fixed window. Rank is not a p-value or causal model probability.
    """
    y, t = s.to_numpy(), s.index.to_numpy(dtype=float)
    t = t - t[0]
    n = len(y)
    if n < 15 or s.isna().any() or not np.array_equal(np.diff(s.index), np.ones(n - 1)):
        return {"status": "refused", "reason": "models need at least 15 consecutive complete seasonal years"}
    if np.ptp(y) == 0:
        return {"status": "constant", "slope_per_year": 0.0, "best_model": "flat", "inferential_claim": False}
    ones = np.ones(n)
    candidates = [("flat", ones[:, None], 1, None),
                  ("trend", np.column_stack([ones, t]), 2, None)]
    episode = ((s.index >= event_start) & (s.index <= event_end)).astype(float)
    if 0 < episode.sum() < n:
        candidates.append(("specified_episode", np.column_stack([ones, episode]), 2, None))
    for k in range(5, n - 4):
        step = (np.arange(n) >= k).astype(float)
        candidates += [("step", np.column_stack([ones, step]), 3, int(s.index[k])),
                       ("step_and_trend", np.column_stack([ones, t, step]), 4, int(s.index[k]))]
    fits = {}
    for label, design, k, boundary in candidates:
        residuals = y - design @ np.linalg.lstsq(design, y, rcond=None)[0]
        ssr = max(float(residuals @ residuals), np.finfo(float).tiny)
        bic = float(n * np.log(ssr / n) + k * np.log(n))
        if label not in fits or bic < fits[label]["bic"]:
            fits[label] = {"bic": bic, "boundary_year": boundary}
    fit = sm.OLS(y, sm.add_constant(t)).fit(cov_type="HAC", cov_kwds={"maxlags": 2})
    ci = fit.conf_int(alpha=0.05)[1]
    residual = fit.resid
    rho = float(np.corrcoef(residual[:-1], residual[1:])[0, 1]) if np.std(residual) > 1e-10 else None
    trim_slopes = [float(stats.theilslopes(y[a:n-b], t[a:n-b]).slope)
                   for a, b in [(0, 0), (3, 0), (0, 3), (3, 3)] if n-a-b >= 10]
    return {"status": "exploratory", "n_years": n, "models": fits,
        "best_model": min(fits, key=lambda k: fits[k]["bic"]),
        "ols_slope_per_year": float(fit.params[1]), "sen_slope_per_year": float(stats.theilslopes(y, t).slope),
        "hac_95_interval": [float(ci[0]), float(ci[1])], "hac_lags": 2,
        "residual_lag1": rho, "endpoint_slope_range": [min(trim_slopes), max(trim_slopes)],
        "limitations": "HAC interval and iid BIC are not calibrated for this weather pipeline; rankings do not establish permanence or absence of change"}


@register("weather_seasons")
def weather_seasons(x: pd.Series, seasons: dict[str, list[int]], baseline_start: int,
                    baseline_end: int, event_start: int, event_end: int,
                    min_baseline_years: int = 15, low_quantile: float = 0.2) -> SkillResult:
    """Compare complete seasons with a fixed pre-event baseline, retaining all values.

    Quantile/15-year cutoffs are disclosed house rules, not WMO drought classes.
    Reference quantiles and sensitivity ranges are not confidence intervals or SPI.
    """
    name = "weather_seasons"
    if x.attrs.get("cadence") != "monthly":
        return refuse(name, "monthly input required", "run weather_monthly first")
    check = weather_audit(x)
    if not check.ok:
        return refuse(name, check.refusal.failed, check.refusal.would_change)
    if not (baseline_start <= baseline_end < event_start <= event_end) or min_baseline_years < 10 or not 0 < low_quantile < 0.5:
        return refuse(name, "invalid baseline/event or threshold settings", "use a non-overlapping earlier baseline, at least 10 years, and a quantile between zero and one half")
    if not seasons:
        return refuse(name, "no seasons supplied", "declare seasons appropriate to the region")
    output, failures = {}, []
    for label, months in seasons.items():
        try:
            s = seasonal_values(x, months)
        except (TypeError, ValueError):
            return refuse(name, f"invalid season specification: {label}", "use ordered contiguous integer months in 1..12")
        baseline = s.reindex(range(baseline_start, baseline_end + 1))
        event = s.reindex(range(event_start, event_end + 1))
        if baseline.isna().any() or len(baseline) < min_baseline_years or event.isna().any():
            failures.append(f"{label}: incomplete baseline/event or fewer than {min_baseline_years} baseline years")
            continue
        mean = float(baseline.mean())
        cutoff = float(baseline.quantile(low_quantile))
        years = []
        for year, value in s.items():
            if pd.isna(value):
                years.append({"year": int(year), "value": None, "status": "incomplete"})
                continue
            years.append({"year": int(year), "value": float(value), "anomaly": float(value - mean),
                "percent_anomaly": float(100 * (value / mean - 1)) if mean > 0 and x.attrs["variable"] == "precipitation" else None,
                "below_baseline_quantile": bool(value < cutoff),
                "baseline_midrank_percentile": float(100 * ((baseline < value).sum() + 0.5 * (baseline == value).sum()) / len(baseline))})
        # Baseline-window sensitivity is an explicit range, not a sampling CI.
        alternatives = [baseline, baseline.iloc[5:], baseline.iloc[:-5]]
        anomalies = [float(event.mean() - b.mean()) for b in alternatives if len(b) >= 10]
        output[label] = {"months": months, "unit": "mm/season" if x.attrs["variable"] == "precipitation" else x.attrs["units"],
            "baseline": [baseline_start, baseline_end], "baseline_n": len(baseline), "baseline_mean": mean,
            "baseline_10_90_reference_range": [float(baseline.quantile(.1)), float(baseline.quantile(.9))],
            "low_quantile": low_quantile, "low_threshold": cutoff,
            "event": [event_start, event_end], "event_mean_anomaly": float(event.mean() - mean),
            "event_below_threshold_count": int((event < cutoff).sum()),
            "baseline_window_anomaly_range": [min(anomalies), max(anomalies)],
            "years": years, "long_term": model_evidence(s, event_start, event_end)}
    if failures:
        return refuse(name, "; ".join(failures), "supply complete baseline and event seasons; do not silently change the baseline or fill rain")
    candidate_years = sorted({s["long_term"]["models"][s["long_term"]["best_model"]]["boundary_year"]
                              for s in output.values() if s["long_term"].get("best_model") in {"step", "step_and_trend"}})
    return SkillResult(name, {"seasons": output, "candidate_years": candidate_years,
        "method_sources": ["schwarz_1978", "scipy_theilslopes", "statsmodels_hac", "weather_policy_v1"],
        "uncertainty": "reference variability, baseline and endpoint sensitivity, exploratory HAC intervals; no calibrated event probability",
        "interpretation": "below-quantile seasons are not automatically severe drought; recovery and an underlying trend can coexist"})
