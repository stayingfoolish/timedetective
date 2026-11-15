"""Load the cached NASA files used by the season check and the water storage check.

Every loader verifies the cached file against the checksum in its sidecar, checks the
fields it relies on against the provider's documentation, and returns a series that
carries its provenance. Nothing is fetched here and nothing is filled in.
"""

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[5]
MASCON_RESOLUTION = 22  # mascons; the provider's stated approximate spatial resolution (about 300 km)
REGIONAL = {
    "PRECTOTCORR_SUM": ("precipitation", "mm/month", "MERRA-2 corrected precipitation, monthly totals, via POWER"),
    "GWETPROF": ("soil_wetness", "fraction of saturation", "MERRA-2 profile soil wetness via POWER"),
}
ACCEPTED_RELIABILITY = (0, 1)  # MOD13 pixel reliability: good, marginal
MIN_GOOD_FRACTION = 0.5


def _card(name: str) -> dict:
    return yaml.safe_load((ROOT / f"knowledge/datasets/earth/{name}.yaml").read_text())


def _verified(path: Path) -> tuple[bytes, dict]:
    """File bytes and sidecar metadata, after checking the checksum. `x.json.gz` and `x.csv` both use `x.meta.yaml`."""
    stem = path.name[: -len(".gz")] if path.suffix == ".gz" else path.name
    meta = yaml.safe_load((path.parent / (Path(stem).stem + ".meta.yaml")).read_text())
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
        raise ValueError(f"checksum mismatch for {path.name}")
    return raw, meta


def load_power_regional(path: Path, parameter: str) -> pd.Series:
    """Box-average monthly series from a POWER monthly regional response (one parameter per file).

    Cells are weighted by the cosine of latitude. A month is missing if any cell is.
    The thirteenth entry of each year is the provider's annual value; for the precipitation
    total it must equal the sum of the twelve months, which confirms the values are monthly
    totals in mm although the service labels them mm/day.
    """
    raw, meta = _verified(path)
    data = json.loads(raw)
    if parameter not in REGIONAL or parameter not in data["parameters"]:
        raise ValueError(f"unsupported or absent parameter: {parameter}")
    variable, units, product = REGIONAL[parameter]
    fill = data["header"]["fill_value"]
    columns, weights = {}, []
    for feature in data["features"]:
        lon, lat = feature["geometry"]["coordinates"][:2]
        values = pd.Series(feature["properties"]["parameter"][parameter], dtype=float).mask(lambda v: v == fill)
        annual = values[values.index.str.endswith("13")]
        months = values[~values.index.str.endswith("13")]
        if parameter == "PRECTOTCORR_SUM":
            sums = months.groupby(months.index.str[:4]).sum(min_count=12)
            check = (sums - annual.rename(lambda k: k[:4])).abs().dropna()
            if len(check) and check.max() > 0.2:
                raise ValueError("annual entries are not the sum of the months; units cannot be confirmed as monthly totals")
        months.index = pd.to_datetime(months.index, format="%Y%m")
        columns[(lat, lon)] = months
        weights.append(np.cos(np.radians(lat)))
    frame = pd.DataFrame(columns)
    w = np.array(weights)
    series = (frame * w).sum(axis=1, min_count=len(w)) / w.sum()
    if not series.index.equals(pd.date_range(series.index[0], series.index[-1], freq="MS")):
        raise ValueError("provider response lacks some months")
    last = int(data["header"]["end"][:4])
    if last >= int(str(meta["retrieved"])[:4]):
        raise ValueError("only completed years are accepted; the latest year can still be revised")
    card = _card("nasa_power_monthly_regional")
    lats, lons = sorted({k[0] for k in columns}), sorted({k[1] for k in columns})
    series.name = parameter
    series.attrs = {
        "variable": variable, "units": units, "cadence": "monthly", "product": product,
        "version": f"POWER API {data['header']['api']['version']}; upstream product version not exposed",
        "source": meta["request_url"], "retrieved": str(meta["retrieved"]), "sha256": meta["sha256"],
        "time_standard": data["header"]["time_standard"],
        "spatial_support": {"kind": "box_mean", "n_cells": len(columns), "cell_centres_south_north": [lats[0], lats[-1]],
                            "cell_centres_west_east": [lons[0], lons[-1]], "weights": "cosine of latitude",
                            "requested_box": {k: meta["region"][k] for k in ("south", "north", "west", "east")}},
        "quality": "provider fill value masked; a month is missing if any cell is; no native quality flags in this export",
        "provider_unit_label": data["parameters"][parameter]["units"], "dataset_card": card["name"],
        "known_issues": card["known_issues"]}
    return series


def load_gsfc_mascons(path: Path) -> pd.Series:
    """Area-weighted regional water-storage series from a mascon subset written by scripts/extract_gsfc_mascons.py.

    Each solution is labelled by the month of the middle of its window. Months without a
    solution stay missing. Regional uncertainty follows the provider's recipe.
    """
    raw, meta = _verified(path)
    frame = pd.read_csv(path)
    areas = {m["mascon_id"]: m["area_km2"] for m in meta["mascons"]}
    if set(frame.mascon_id) != set(areas) or frame.groupby("mid_date").mascon_id.nunique().ne(len(areas)).any():
        raise ValueError("a solution lacks some of the region's mascons")
    frame["area"] = frame.mascon_id.map(areas)
    total = sum(areas.values())
    by_date = frame.groupby("mid_date").apply(
        lambda g: pd.Series({"cmwe": (g.cmwe * g.area).sum() / total, "noise": (g.noise_2sigma_cm * g.area).sum() / total}),
        include_groups=False)
    by_date.index = pd.to_datetime(by_date.index)
    months = by_date.index.to_period("M")
    doubled = sorted({str(m) for m in months[months.duplicated()]})
    monthly = by_date.groupby(months).mean()
    index = pd.date_range(monthly.index[0].to_timestamp(), monthly.index[-1].to_timestamp(), freq="MS")
    series = monthly["cmwe"].set_axis(monthly.index.to_timestamp()).reindex(index)
    n, z = len(areas), MASCON_RESOLUTION
    shrink = np.sqrt(n / min(z, n))
    card = _card("gsfc_grace_mascons")
    spans = [(m["lat_center"] - m["lat_span"] / 2, m["lat_center"] + m["lat_span"] / 2,
              m["lon_center"] - m["lon_span"] / 2, m["lon_center"] + m["lon_span"] / 2) for m in meta["mascons"]]
    series.name = meta["name"]
    series.attrs = {
        "variable": "water_storage_anomaly", "units": meta["units"], "cadence": "monthly", "product": meta["product"],
        "version": "RL06v2.0", "source": meta["source"], "retrieved": str(meta["retrieved"]), "sha256": meta["sha256"],
        "source_sha256": meta["source_sha256"], "time_standard": "solution windows labelled by the month of their middle day",
        "storage_kind": "total_water_storage", "baseline": meta["baseline"],
        "resolution_units": n, "min_resolution_units": z, "area_km2": float(total),
        "spatial_support": {"kind": "mascon_union", "n_mascons": n, "area_km2": float(total), "selection": meta["selection"],
                            "footprint": {"south": min(s[0] for s in spans), "north": max(s[1] for s in spans),
                                          "west": min(s[2] for s in spans), "east": max(s[3] for s in spans)}},
        "quality": "every mascon required for each solution; months without a solution are missing; nothing filled",
        "months_with_two_solutions": doubled,
        "provider_uncertainty": {
            "leakage_trend_cm_per_year": float(abs(sum(m["leakage_trend_cm_per_year"] * m["area_km2"] for m in meta["mascons"])) / total),
            "leakage_2sigma_cm": float(sum(m["leakage_2sigma_cm"] * m["area_km2"] for m in meta["mascons"]) / total / shrink),
            "median_noise_2sigma_cm": float(by_date["noise"].median() / shrink),
            "recipe": "provider format description: regional means, stochastic terms divided by sqrt(N/22)"},
        "dataset_card": card["name"], "known_issues": card["known_issues"]}
    return series


def load_modis_subset(path: Path) -> pd.Series:
    """Vegetation-index composites averaged over the box, from a cached bundle of ORNL DAAC subset responses.

    A pixel is kept if its reliability rank is 0 or 1 and its value is inside the valid range.
    A composite with fewer than half its pixels kept is missing. Composite dates are the
    provider's calendar dates (the first day of each 16-day period).
    """
    raw, meta = _verified(path)
    bundle = json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)
    ndvi, quality, header = {}, {}, None
    for response in bundle["responses"]:
        body = json.loads(response["body"])
        header = header or body
        if body["ncols"] != header["ncols"] or body["nrows"] != header["nrows"]:
            raise ValueError("responses cover different pixel grids")
        target = ndvi if body["band"] == "250m_16_days_NDVI" else quality if body["band"] == "250m_16_days_pixel_reliability" else None
        if target is None:
            raise ValueError(f"unexpected band {body['band']}")
        for item in body["subset"]:
            target[item["calendar_date"]] = np.asarray(item["data"], dtype=float)
    expected = {d["calendar_date"] for d in json.loads(bundle["dates"]["body"])["dates"]}
    if set(ndvi) != expected or set(quality) != expected:
        raise ValueError("the bundle does not hold every composite date the provider lists")
    scale = float(header["scale"])
    rows = {}
    for day in sorted(ndvi):
        values, ranks = ndvi[day], quality[day]
        keep = np.isin(ranks, ACCEPTED_RELIABILITY) & (values >= -2000) & (values <= 10000)
        fraction = float(keep.mean())
        rows[day] = (float(values[keep].mean() * scale) if fraction >= MIN_GOOD_FRACTION else np.nan, fraction)
    series = pd.Series({pd.Timestamp(k): v[0] for k, v in rows.items()}, name="NDVI")
    fractions = np.array([v[1] for v in rows.values()])
    card = _card("modis_ndvi_subset")
    series.attrs = {
        "variable": "vegetation_index", "units": "NDVI", "cadence": "16-day composite",
        "product": f"{meta['product']} via ORNL DAAC TESViS", "version": "as served; collection not exposed by the subset response",
        "source": meta["source"], "retrieved": str(meta["retrieved"]), "sha256": meta["sha256"], "time_standard": "composite start date",
        "spatial_support": {"kind": "box_mean", "latitude": header["latitude"], "longitude": header["longitude"],
                            "km_above_below": meta["km_above_below"], "km_left_right": meta["km_left_right"],
                            "n_pixels": int(header["ncols"] * header["nrows"]), "cell_size_m": header["cellsize"]},
        "quality": (f"pixels with reliability rank in {list(ACCEPTED_RELIABILITY)} and a valid value; a composite needs "
                    f"{int(100 * MIN_GOOD_FRACTION)}% of pixels kept, otherwise it is missing"),
        "composites": len(series), "composites_missing": int(series.isna().sum()),
        "median_fraction_of_pixels_kept": float(np.median(fractions)),
        "dataset_card": card["name"], "known_issues": card["known_issues"]}
    return series
