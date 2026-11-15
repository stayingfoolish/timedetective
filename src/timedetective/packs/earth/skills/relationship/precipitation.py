"""Paired-product discrepancies, never ground-truth accuracy or independent replication."""

import numpy as np
import pandas as pd

from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse
from ..diagnostics.weather import weather_audit


@register("weather_precip_agreement")
def weather_precip_agreement(x: pd.Series, *, companion: pd.Series | None,
                            analyses: list[str], wet_threshold: float) -> SkillResult:
    """Aligned daily discrepancy and wet-day agreement without significance or truth labels."""
    name = "weather_precip_agreement"
    if "agreement" not in analyses:
        return SkillResult(name, {"status": "not_requested"})
    if companion is None:
        return refuse(name, "companion product unavailable", "supply both products at the same requested support")
    for record in [x, companion]:
        check = weather_audit(record, "extremes")
        if not check.ok:
            return refuse(name, check.refusal.failed, check.refusal.would_change)
    if x.attrs["spatial_support"] != companion.attrs["spatial_support"] or x.attrs["time_standard"] != companion.attrs["time_standard"]:
        return refuse(name, "spatial/time supports differ", "align requested coordinates and daily boundaries")
    paired = pd.concat([x.rename("a"),companion.rename("b")],axis=1,join="inner")
    if len(paired) < 365 or paired.isna().to_numpy().any():
        return refuse(name, "need at least 365 complete paired days", "supply aligned complete daily records; do not silently drop missing pairs")
    a,b = paired.a.to_numpy(),paired.b.to_numpy()
    difference = a-b
    wet_a,wet_b = a >= wet_threshold,b >= wet_threshold
    correlation = float(np.corrcoef(a,b)[0,1]) if np.std(a)>0 and np.std(b)>0 else None
    return SkillResult(name, {"paired_days":len(paired),"overlap":[str(paired.index[0].date()),str(paired.index[-1].date())],
        "primary_mean_mm_per_day":float(a.mean()),"companion_mean_mm_per_day":float(b.mean()),
        "primary_minus_companion_mm_per_day":float(difference.mean()),
        "rmse_between_products_mm_per_day":float(np.sqrt(np.mean(difference**2))),
        "mae_between_products_mm_per_day":float(np.mean(np.abs(difference))),"pearson_r":correlation,
        "wet_threshold_mm_per_day":wet_threshold,"both_wet_days":int((wet_a & wet_b).sum()),
        "primary_only_wet_days":int((wet_a & ~wet_b).sum()),"companion_only_wet_days":int((~wet_a & wet_b).sum()),
        "both_dry_days":int((~wet_a & ~wet_b).sum()),
        "native_footprints":[x.attrs.get("spatial_resolution"),companion.attrs.get("spatial_resolution")],
        "independence_established":False,
        "limitations":"Signed difference and RMSE measure product disagreement, not bias/error against truth. Correlation is descriptive and not independent validation. Native grid footprints may differ.",
        "method_sources":["precipitation_policy_v2","imerg_atbd_2023"]})
