"""GLDAS soil, snow and canopy water over a GRACE region, and the groundwater estimate made with it.

The subtraction follows Rodell et al. (2009): groundwater change = satellite total water storage
change minus modelled soil and snow water. Nothing is fetched or filled here.
"""

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from timedetective.packs.earth.adapters.stories import _card, _verified

BASELINE = ("2004-01-01", "2009-12-01")  # the GRACE provider's 2004.0-2010.0 mean, as monthly labels
MIN_CELLS_FRACTION = 0.5


def _footprints(mascon_meta: dict) -> list[tuple[float, float, float, float, float]]:
    return [(m["lat_center"] - m["lat_span"] / 2, m["lat_center"] + m["lat_span"] / 2,
             m["lon_center"] - m["lon_span"] / 2, m["lon_center"] + m["lon_span"] / 2, m["area_km2"])
            for m in mascon_meta["mascons"]]


def load_gldas_storage(path: Path, mascon_meta_path: Path) -> pd.Series:
    """Monthly soil + snow + canopy water (cm), averaged over the same mascon footprints as the GRACE region.

    Each mascon takes the mean of the grid cells whose centres fall inside it; a mascon with
    fewer than half its cells reported makes that month missing. Mascons are weighted by area,
    as the GRACE regional series is. Returned as anomalies from the 2004.0-2010.0 mean.
    """
    raw, meta = _verified(path)
    bundle = json.loads(gzip.decompress(raw))
    mascons = yaml.safe_load(mascon_meta_path.read_text())
    if meta["region"] != mascons["name"].removeprefix("gsfc_mascons_"):
        raise ValueError("the GLDAS bundle was cut for a different region")
    lat, lon = np.asarray(bundle["lat"]), np.asarray(bundle["lon"])
    footprints = _footprints(mascons)
    masks = [((lat >= s) & (lat < n))[:, None] & ((lon >= w) & (lon < e))[None, :] for s, n, w, e, _ in footprints]
    if any(not m.any() for m in masks):
        raise ValueError("a mascon footprint has no GLDAS cells in the bundle")
    weights = np.array([f[4] for f in footprints])
    values = {}
    for month, grids in sorted(bundle["months"].items()):
        total = sum(np.array(grids[v], dtype=float) for v in bundle["variables"])  # None -> nan, and nan propagates
        per_mascon = []
        for mask in masks:
            cells = total[mask]
            per_mascon.append(np.nanmean(cells) if np.isfinite(cells).mean() >= MIN_CELLS_FRACTION else np.nan)
        per_mascon = np.array(per_mascon)
        values[pd.Timestamp(f"{month[:4]}-{month[4:]}-01")] = (
            float((per_mascon * weights).sum() / weights.sum()) / 10 if np.isfinite(per_mascon).all() else np.nan)
    series = pd.Series(values, name=meta["name"]).asfreq("MS")
    baseline = series[BASELINE[0]:BASELINE[1]]
    if baseline.isna().any() or len(baseline) != 72:
        raise ValueError("the baseline period is incomplete")
    series = series - baseline.mean()
    card = _card("gldas_noah_monthly")
    series.attrs = {
        "variable": "modelled_land_storage_anomaly", "units": "cm equivalent water height", "cadence": "monthly",
        "product": meta["product"], "version": "2.1", "source": meta["source"], "retrieved": str(meta["retrieved"]),
        "sha256": meta["sha256"], "time_standard": "calendar month", "components": bundle["variables"],
        "baseline": "mean over 2004.0-2010.0 removed", "spatial_support": {"kind": "mascon_union", "region": meta["region"],
                                                                          "n_mascons": len(footprints)},
        "quality": "a mascon needs half its cells reported; a month needs every mascon; nothing filled",
        "dataset_card": card["name"], "known_issues": card["known_issues"]}
    return series


def groundwater_estimate(total: pd.Series, modelled: pd.Series) -> pd.Series:
    """Total water storage minus modelled soil, snow and canopy water, month by month (Rodell et al. 2009).

    Months are paired by label; a month missing from either record stays missing. The result is
    labelled groundwater and records what was subtracted and what was not (surface water).
    """
    if total.attrs.get("storage_kind") != "total_water_storage":
        raise ValueError("the first series must be total water storage")
    if modelled.attrs.get("variable") != "modelled_land_storage_anomaly":
        raise ValueError("the second series must be modelled soil, snow and canopy water")
    if total.attrs["spatial_support"].get("n_mascons") != modelled.attrs["spatial_support"].get("n_mascons"):
        raise ValueError("the two records cover different regions")
    paired = modelled.reindex(total.index)
    out = (total - paired).rename(f"{total.name}_minus_gldas")
    subtracted = paired.groupby(paired.index.year).mean()
    out.attrs = {**total.attrs, "storage_kind": "groundwater",
                 "sha256": f"{total.attrs['sha256']}+{modelled.attrs['sha256']}",
                 "product": f"{total.attrs['product']} minus {modelled.attrs['product']} soil, snow and canopy water",
                 "lineage": [total.attrs["sha256"], modelled.attrs["sha256"]],
                 "subtraction": {"method": "total water storage minus modelled soil moisture (0-200 cm), snow and canopy water",
                                 "model": modelled.attrs["product"], "model_sha256": modelled.attrs["sha256"],
                                 "not_subtracted": "surface water (lakes, rivers, reservoirs, canals) was not subtracted, because the model has no such store",
                                 "subtracted_yearly_mean_cm": {int(y): float(v) for y, v in subtracted.dropna().items()}},
                 "companion_dataset_card": modelled.attrs["dataset_card"]}
    return out
