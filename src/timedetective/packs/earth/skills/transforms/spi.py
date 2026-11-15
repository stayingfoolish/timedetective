"""Calendar-stratified zero-adjusted gamma SPI with explicit fit/record safeguards."""

import numpy as np
import pandas as pd
from scipy import stats

from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse
from ..diagnostics.weather import weather_audit
from ..diagnostics.precipitation import runs


@register("weather_precip_spi")
def weather_precip_spi(x: pd.Series, *, analyses: list[str], baseline: list[int],
                      scale: int, seed: int, fit_resamples: int) -> SkillResult:
    """Gamma MLE per ending calendar month; q+(1-q)G mapped with normal PPF.

    The 30-year/20-positive baseline and fit-screen cutoffs are disclosed policy.
    Gamma MLE is not Copernicus's L-moment estimator; no claimed numerical identity.
    """
    name = "weather_precip_spi"
    if "spi" not in analyses:
        return SkillResult(name, {"status": "not_requested"})
    audit = weather_audit(x)
    if not audit.ok:
        return refuse(name, audit.refusal.failed, audit.refusal.would_change)
    if x.attrs.get("cadence") != "monthly" or x.attrs.get("units") != "mm/month" or x.attrs.get("variable") != "precipitation":
        return refuse(name, "monthly precipitation totals required", "run weather_monthly")
    if not 1 <= scale <= 24 or not 99 <= fit_resamples <= 999 or baseline[1]-baseline[0]+1 < 30:
        return refuse(name, "SPI needs at least 30 baseline years, scale 1..24 and 99..999 fit resamples", "use a longer reference record; do not relabel empirical ranks as SPI")
    accumulated = x.rolling(scale, min_periods=scale).sum()
    output = pd.Series(np.nan, index=x.index)
    fits, failures, clipped = {}, [], 0
    for month in range(1, 13):
        dates = pd.to_datetime([f"{year}-{month:02d}-01" for year in range(baseline[0], baseline[1]+1)])
        base = accumulated.reindex(dates)
        positive = base[base > 0].to_numpy()
        if base.isna().any() or len(positive) < 20 or np.ptp(positive) <= 0:
            failures.append(f"month {month}: incomplete accumulation baseline or insufficient nonconstant positive totals")
            continue
        shape, loc, theta = stats.gamma.fit(positive, floc=0)
        q = float((base == 0).mean())
        gof = stats.goodness_of_fit(stats.gamma, positive, known_params={"loc": 0},
            statistic="ks", n_mc_samples=fit_resamples, rng=np.random.default_rng(seed+month))
        fits[str(month)] = {"shape": float(shape), "scale": float(theta), "zero_probability": q,
            "n": len(base), "positive_n": len(positive), "gof_p": float(gof.pvalue)}
        if gof.pvalue < .01:
            failures.append(f"month {month}: gamma fit rejected at policy screening threshold .01")
            continue
        mask = accumulated.index.month == month
        values = accumulated[mask]
        probability = q + (1-q) * stats.gamma.cdf(values.to_numpy(), shape, loc=loc, scale=theta)
        clipped += int(np.count_nonzero((probability < 1e-8) | (probability > 1-1e-8)))
        output.loc[mask] = stats.norm.ppf(np.clip(probability, 1e-8, 1-1e-8))
    events = []
    for a, b in runs((output < 0).to_numpy()):
        segment = output.iloc[a:b+1]
        if segment.min() > -1:
            continue
        events.append({"start": str(output.index[a].date()), "end": str(output.index[b].date()),
            "months": b-a+1, "minimum_spi": float(segment.min()), "magnitude": float(-segment.sum()),
            "left_censored": bool(a == 0 or pd.isna(output.iloc[a-1])),
            "right_censored": bool(b == len(output)-1 or pd.isna(output.iloc[b+1]))})
    return SkillResult(name, {"scale_months": scale, "baseline": baseline, "fits": fits,
        "series": [{"date": str(d.date()), "spi": None if pd.isna(v) else float(v)} for d, v in output.items()],
        "drought_events": events, "clipped_probability_count": clipped, "probability_clip": [1e-8, 1-1e-8],
        "subprocedure_refusals": [{"procedure": name, "failed": f, "would_change": "provide adequate baseline support or validate an alternative distribution"} for f in failures],
        "limitations": "Model-based index, not a calibrated drought probability or impact forecast. Overlapping accumulations are dependent. Zero totals use the upper CDF mass q; arid-season severity is limited. Fit screens assume independent baseline years.",
        "method_sources": ["copernicus_spi", "idmp_spi", "scipy_gamma", "scipy_gof", "precipitation_policy_v2"]})
