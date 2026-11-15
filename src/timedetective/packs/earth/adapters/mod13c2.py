"""Monthly regional greenness over a GRACE story region, from per-mascon MOD13C2 summaries.

Nothing is fetched or filled here; the summaries are written by scripts/fetch_mod13c2_regions.py.
"""

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from timedetective.packs.earth.adapters.stories import _card, _verified

MIN_KEPT_FRACTION = 0.5
MAX_FAILING_SHARE = 0.25  # a mascon failing the quality rule in more months than this is left out for the whole record


def load_mod13c2_region(path: Path, mascon_meta_path: Path) -> pd.Series:
    """Area-weighted mean NDVI over the region's mascons, month by month.

    A mascon with fewer than half its cells kept (reliability 0 or 1) fails that month. A mascon
    that fails in more than a quarter of months (in practice: snow-covered every winter) is left
    out for the whole record and named, so the average does not change composition by season.
    Every remaining mascon is then needed each month. Skipped granules stay missing.
    """
    raw, meta = _verified(path)
    bundle = json.loads(gzip.decompress(raw))
    mascons = yaml.safe_load(mascon_meta_path.read_text())
    if meta["region"] != mascons["name"].removeprefix("gsfc_mascons_"):
        raise ValueError("the NDVI bundle was cut for a different region")
    areas = {m["mascon_id"]: m["area_km2"] for m in mascons["mascons"]}
    def passes(r: dict) -> bool:
        return bool(r["n_cells"]) and r["n_kept"] / r["n_cells"] >= MIN_KEPT_FRACTION and r["mean_ndvi"] is not None

    for month, rows in bundle["months"].items():
        if {r["mascon_id"] for r in rows} != set(areas):
            raise ValueError(f"{month}: summaries do not cover the region's mascons")
    n_months = len(bundle["months"])
    failing = {m: sum(not passes(r) for rows in bundle["months"].values() for r in rows if r["mascon_id"] == m) / n_months
               for m in areas}
    excluded = {m: share for m, share in failing.items() if share > MAX_FAILING_SHARE}
    used = {m: a for m, a in areas.items() if m not in excluded}
    values = {}
    for month, rows in sorted(bundle["months"].items()):
        ok = [r for r in rows if r["mascon_id"] in used and passes(r)]
        stamp = pd.Timestamp(f"{month[:4]}-{month[4:]}-01")
        if len(ok) == len(used):
            weights = np.array([used[r["mascon_id"]] for r in ok])
            values[stamp] = float(np.dot([r["mean_ndvi"] for r in ok], weights) / weights.sum())
        else:
            values[stamp] = np.nan
    for item in bundle.get("skipped", []):
        values.setdefault(pd.Timestamp(f"{item['month']}-01"), np.nan)
    series = pd.Series(values, name=meta["name"]).sort_index().asfreq("MS")
    card = _card("modis_ndvi_monthly_cmg")
    series.attrs = {
        "variable": "vegetation_index", "units": "NDVI", "cadence": "monthly composite", "product": meta["product"],
        "version": "061", "source": meta["source"], "retrieved": str(meta["retrieved"]), "sha256": meta["sha256"],
        "time_standard": "calendar month",
        "spatial_support": {"kind": "mascon_union", "region": meta["region"], "n_mascons": len(used),
                            "area_km2": float(sum(used.values())), "share_of_storage_region_area": float(sum(used.values()) / sum(areas.values()))},
        "excluded_mascons": [{"mascon_id": m, "share_of_months_failing": float(share),
                              "reason": "fails the quality rule (snow, cloud) in more than a quarter of months"} for m, share in excluded.items()],
        "quality": "cells with reliability 0 or 1; a mascon needs half its cells kept; a month needs every mascon; nothing filled",
        "skipped_months": [s["month"] for s in bundle.get("skipped", [])],
        "dataset_card": card["name"], "known_issues": card["known_issues"]}
    return series
