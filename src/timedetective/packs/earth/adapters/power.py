"""Load immutable NASA POWER daily responses with verified provenance."""

import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

PARAMETERS = {
    "PRECTOTCORR": ("precipitation", "mm/day", "MERRA-2 corrected precipitation via POWER", ["MERRA2", "gauge-informed"]),
    "IMERG_PRECTOT": ("precipitation", "mm/day", "IMERG precipitation via POWER", ["IMERG", "gauge-informed", "MERRA2 ancillary"]),
    "T2M": ("temperature", "C", "MERRA-2 temperature via POWER", ["MERRA2"]),
    "WS10M": ("wind_speed", "m/s", "MERRA-2 wind via POWER", ["MERRA2"]),
    "RH2M": ("relative_humidity", "%", "MERRA-2 humidity via POWER", ["MERRA2"]),
    "PS": ("surface_pressure", "kPa", "MERRA-2 pressure via POWER", ["MERRA2"]),
}


def load_power(path: Path, parameter: str, sidecar: Path | None = None) -> pd.Series:
    """Validate checksum/units/time standard before returning a metadata-bearing series."""
    meta = yaml.safe_load((sidecar or path.with_suffix(".meta.yaml")).read_text())
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != meta["sha256"]:
        raise ValueError("raw data checksum mismatch")
    data = json.loads(raw)
    variable, unit, product, lineage = PARAMETERS[parameter]
    actual_unit = data["parameters"][parameter]["units"]
    # POWER docs describe IMERG daily sums as mm; the observed API returns mm/day.
    if actual_unit != unit and not (parameter == "IMERG_PRECTOT" and actual_unit == "mm"):
        raise ValueError(f"unexpected provider unit: {actual_unit}")
    if data["header"]["time_standard"] != "UTC":
        raise ValueError("this adapter requires UTC daily boundaries")
    values = data["properties"]["parameter"][parameter]
    series = pd.Series(values, dtype=float)
    series.index = pd.to_datetime(series.index, format="%Y%m%d")
    if series.index.has_duplicates or not series.index.is_monotonic_increasing:
        raise ValueError("provider dates are duplicate or unsorted")
    series = series.mask(series == data["header"]["fill_value"])
    start = pd.to_datetime(data["header"]["start"], format="%Y%m%d")
    end = pd.to_datetime(data["header"]["end"], format="%Y%m%d")
    if not series.index.equals(pd.date_range(start, end, freq="D")):
        raise ValueError("provider response lacks requested daily timestamps")
    if end.year >= int(meta["retrieved"][:4]):
        raise ValueError("near-real-time mixed/revised products are not supported by this frozen historical adapter")
    lon, lat = data["geometry"]["coordinates"][:2]
    root = Path(__file__).resolve().parents[5]
    card_name = "nasa_power_imerg" if parameter.startswith("IMERG") else "nasa_power_daily"
    card = yaml.safe_load((root / f"knowledge/datasets/earth/{card_name}.yaml").read_text())
    series.name = parameter
    series.attrs = {"variable": variable, "units": unit, "cadence": "daily", "product": product,
        "version": f"POWER API {data['header']['api']['version']}; upstream product version not exposed",
        "source": meta["request_url"], "retrieved": meta["retrieved"], "sha256": digest,
        "time_standard": "UTC", "spatial_support": {"kind": "point_query", "latitude": lat, "longitude": lon},
        "spatial_resolution": "0.1 degree" if parameter.startswith("IMERG") else "0.5 latitude x 0.625 longitude degree",
        "quality": "provider fill value masked; per-day native quality flags unavailable in this export",
        "lineage": lineage, "dataset_card": card_name, "known_issues": card["known_issues"],
        "limitations": [
            "POWER is a derivative export; native versions and retrieval quality flags need separate verification.",
            "A point query samples a grid footprint, not a rain gauge or regional mean.",
            "MERRA-2 and IMERG can share ancillary and gauge information; independence is not established."]}
    return series
