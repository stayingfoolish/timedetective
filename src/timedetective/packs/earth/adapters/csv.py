"""Provider-neutral offline import; explicit metadata, QC and spatial weights required."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def load_csv(path: Path) -> pd.Series:
    """Read date/value or date/cell_id/value/weight_km2 CSV plus .meta.yaml.

    Weights must already be clipped cell areas for a declared polygon. Missing
    cells make the area mean missing; no changing spatial support or renormalization.
    """
    raw = path.read_bytes()
    meta = yaml.safe_load(path.with_suffix(".meta.yaml").read_text())
    if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
        raise ValueError("CSV checksum mismatch")
    frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame["value"] = pd.to_numeric(frame["value"], errors="raise")
    frame.loc[frame.value.isin(meta.get("missing_values", [])), "value"] = np.nan
    if "quality_flag" in frame:
        if "accepted_quality_flags" not in meta:
            raise ValueError("quality flags present but acceptance rules absent")
        frame.loc[~frame.quality_flag.isin(meta["accepted_quality_flags"]), "value"] = np.nan
    if "cell_id" in frame:
        if meta.get("spatial_support", {}).get("kind") != "polygon" or not meta.get("weights_source"):
            raise ValueError("gridded data require a declared polygon and source for clipped area weights")
        if frame.duplicated(["date", "cell_id"]).any():
            raise ValueError("duplicate cell-date observations")
        if "weight_km2" not in frame or not np.isfinite(frame.weight_km2).all() or (frame.weight_km2 <= 0).any():
            raise ValueError("positive finite clipped cell areas required")
        if frame.groupby("cell_id").weight_km2.nunique().max() != 1:
            raise ValueError("time-varying spatial weights are unsupported")
        weights = frame.groupby("cell_id").weight_km2.first()
        wide = frame.pivot(index="date", columns="cell_id", values="value").reindex(columns=weights.index)
        series = wide.mul(weights).sum(axis=1, min_count=len(weights)) / weights.sum()
        meta = {**meta, "aggregation": "fixed clipped-area weighted mean; every cell required",
                "pixel_count": len(weights), "area_km2": float(weights.sum()),
                "incomplete_spatial_timestamps": int(wide.isna().any(axis=1).sum())}
    else:
        if frame.date.duplicated().any() or not frame.date.is_monotonic_increasing:
            raise ValueError("duplicate or unsorted dates")
        series = frame.set_index("date").value
    series.name = meta.get("name", path.stem)
    series.attrs = meta
    return series
