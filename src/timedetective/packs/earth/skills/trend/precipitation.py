"""Dependent-data resampling statistics; finite-sample validity is evaluated separately."""

import numpy as np
import pandas as pd
from scipy import stats

from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse
from ..diagnostics.weather import weather_audit
from .seasonal import seasonal_values
from ..diagnostics.weather import weather_extremes
from ..transforms.monthly import weather_monthly


def stationary_indices(n: int, repetitions: int, length: int, seed: int) -> np.ndarray:
    """Politis–Romano (1994): restart uniformly with probability 1/length, else wrap."""
    if n < 2 or repetitions < 1 or not 1 <= length <= n or type(seed) is not int or seed < 0:
        raise ValueError("invalid bootstrap dimensions/seed")
    rng = np.random.default_rng(seed)
    index = rng.integers(n, size=(repetitions, n))
    restart = rng.random((repetitions, n)) < 1 / length
    for j in range(1, n):
        index[:, j] = np.where(restart[:, j], index[:, j], (index[:, j - 1] + 1) % n)
    return index


def dependent_test(y: np.ndarray, *, method: str, seed: int, resamples: int,
                   alpha: float = .05, contrast: np.ndarray | None = None) -> dict:
    """Stationary-null bootstrap; max over block sensitivities, not a calibrated guarantee.

    Composite test/interval construction is precipitation_policy_v2, not a claim
    that Politis–Romano directly validate short, skewed precipitation records.
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 20 or not np.isfinite(y).all() or np.ptp(y) == 0:
        raise ValueError("need at least 20 consecutive, finite, nonconstant seasonal years")
    if not 199 <= resamples <= 9999 or not 0 < alpha <= .05:
        raise ValueError("resamples must be 199..9999 and alpha in (0,.05]")
    t = np.arange(n, dtype=float) - (n - 1) / 2
    lengths = sorted({2, max(2, round(n ** (1 / 3))), max(2, min(n // 4, 2 * round(n ** (1 / 3))))})
    breaks = np.arange(8, n - 7)
    if method == "trend":
        weights = t / (t @ t)
        estimate = float(y @ weights)
        residual = y - y.mean() - estimate * t
    elif method == "period_change":
        if contrast is None or len(contrast) != n or not np.isclose(contrast.sum(), 0):
            raise ValueError("invalid prespecified period contrast")
        weights = contrast
        estimate = float(y @ weights)
        residual = y - y.mean()
    elif method == "changepoint":
        # Maximum absolute standardized mean contrast over ALL admissible boundaries.
        weights = np.array([np.r_[np.full(k, -1 / k), np.full(n-k, 1 / (n-k))] /
                            np.sqrt(1 / k + 1 / (n-k)) for k in breaks])
        contrasts = weights @ y
        selected = int(np.argmax(np.abs(contrasts)))
        estimate = float(contrasts[selected])
        residual = y - y.mean()
    else:
        raise ValueError("unknown dependent test")
    sensitivities = []
    for length in lengths:
        idx = stationary_indices(n, resamples, length, seed + length)
        null = (y - y.mean())[idx]  # stationary no-change null; never iid daily shuffling
        if method == "changepoint":
            sampled = np.max(np.abs(null @ weights.T), axis=1)
        else:
            sampled = np.abs(null @ weights)
        p = float((1 + np.count_nonzero(sampled >= abs(estimate) - 1e-12)) / (resamples + 1))
        interval = None
        if method == "trend":
            error = residual[idx] @ weights
            interval = [float(estimate - np.quantile(error, 1-alpha/2)),
                        float(estimate - np.quantile(error, alpha/2))]
        sensitivities.append({"mean_block_years": length, "p_value": p, "basic_interval": interval})
    out = {"method": method, "n_years": n, "estimate": estimate,
        "p_value": max(v["p_value"] for v in sensitivities), "block_sensitivity": sensitivities,
        "seed": seed, "resamples": resamples, "alpha": alpha,
        "p_value_resolution": 1 / (resamples + 1),
        "assumptions": "stationary short-memory no-change null; fixed seasons and record; no missing years",
        "inference_status": "experimental_failed_dependence_calibration",
        "validation_note": "The fixed 500-replicate audit exceeded the 5% false-positive target under persistent and long-memory nulls; see docs/precipitation_validation.md.",
        "limitations": "Long memory, evolving variance and observing changes can invalidate the null; non-rejection is not equivalence."}
    if method == "trend":
        out.update(sen_slope=float(stats.theilslopes(y).slope), unit="mm/season/year",
                   interval=[min(v["basic_interval"][0] for v in sensitivities),
                             max(v["basic_interval"][1] for v in sensitivities)])
    elif method == "period_change":
        out.update(unit="mm/season", interval=None,
                   interval_limitation="No difference interval issued: unequal-period dependence needs separate interval calibration.")
    else:
        k = int(breaks[selected])
        out.update(boundary_index=k, before_mean=float(y[:k].mean()), after_mean=float(y[k:].mean()),
                   searched_boundaries=len(breaks), boundary_uncertainty="not estimated; selected year is not a precise causal date",
                   alternative="departure from a constant mean; a smooth trend may also trigger this test")
    return out


@register("weather_precip_inference")
def weather_precip_inference(x: pd.Series, *, method: str, analyses: list[str],
                            seasons: dict[str, list[int]], baseline: list[int], event: list[int],
                            seed: int, resamples: int, alpha: float, target: str = "seasonal_total") -> SkillResult:
    """Apply one requested test to each prespecified season; preserve every failed member."""
    name = "weather_precip_inference"
    if method not in analyses:
        return SkillResult(name, {"status": "not_requested", "tests": []})
    audit = weather_audit(x)
    if not audit.ok:
        return refuse(name, audit.refusal.failed, audit.refusal.would_change)
    if x.attrs.get("variable") != "precipitation":
        return refuse(name, "precipitation required", "supply precipitation observations")
    daily = None
    if target != "seasonal_total":
        daily = weather_extremes(x)
        if not daily.ok:
            return refuse(name, daily.refusal.failed, daily.refusal.would_change)
    else:
        monthly = weather_monthly(x)
        if not monthly.ok:
            return refuse(name, monthly.refusal.failed, monthly.refusal.would_change)
        x = monthly.series
    tests, failures = [], []
    for label, months in seasons.items():
        try:
            excluded = []
            unit = "mm/season"
            if target == "seasonal_total":
                s = seasonal_values(x, months)
                # Only incomplete boundary seasons may be excluded, and are reported.
                while len(s) and pd.isna(s.iloc[0]):
                    excluded.append(int(s.index[0]))
                    s = s.iloc[1:]
                while len(s) and pd.isna(s.iloc[-1]):
                    excluded.append(int(s.index[-1]))
                    s = s.iloc[:-1]
            else:
                keys = {"rx1day": ("rx1day_mm", "mm"), "rx5day": ("rx5day_within_year_mm", "mm"),
                        "wet_days": ("wet_days", "days"), "dry_spell": ("cdd_within_year_days", "days"),
                        "sdii": ("sdii_mm_per_wet_day", "mm/wet_day")}
                if target not in keys or months != list(range(1, 13)):
                    raise ValueError("unknown target or nonannual daily-index inference")
                key, unit = keys[target]
                s = pd.Series({r["year"]: r[key] for r in daily.values["annual_indices"]}, dtype=float)
                excluded = daily.values["excluded_years"]
                if excluded:
                    raise ValueError("daily-index inference refuses incomplete years")
            if not len(s) or s.isna().any() or not np.array_equal(np.diff(s.index), np.ones(len(s)-1)):
                raise ValueError("incomplete seasonal years; choose a fully supported record/season")
            contrast = None
            if method == "period_change":
                before = (s.index >= baseline[0]) & (s.index <= baseline[1])
                after = (s.index >= event[0]) & (s.index <= event[1])
                if before.sum() != baseline[1]-baseline[0]+1 or after.sum() != event[1]-event[0]+1:
                    raise ValueError("requested baseline/event extends outside complete seasonal support")
                if before.sum() < 10 or after.sum() < 10 or np.any(before & after):
                    raise ValueError("period inference needs at least 10 complete disjoint years in each specified period")
                contrast = after.astype(float) / after.sum() - before.astype(float) / before.sum()
            result = dependent_test(s.to_numpy(), method=method, seed=seed,
                                    resamples=resamples, alpha=alpha, contrast=contrast)
            result.update(id=f"{method}:{label}", season=label, years=[int(v) for v in s.index])
            result.update(target=target, excluded_boundary_years=excluded,
                          unit=f"{unit}/year" if method == "trend" else unit)
            if method == "changepoint":
                result["boundary_year"] = int(s.index[result["boundary_index"]])
            tests.append(result)
        except (ValueError, TypeError) as exc:
            failures.append({"procedure": name, "failed": f"{method}/{label}: {exc}",
                "would_change": "provide a sufficiently long complete record; never replace missing rainfall with zero"})
    return SkillResult(name, {"tests": tests, "subprocedure_refusals": failures,
        "method_sources": ["politis_romano_1994", "arch_stationary", "precipitation_policy_v2", "scipy_theilslopes"]})
