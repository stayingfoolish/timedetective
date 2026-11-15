"""Cut a regional subset out of the NASA GSFC GRACE/GRACE-FO mascon file.

The global file is about 174 MB, so it is not committed. This script records its
checksum and writes the mascons whose centres fall inside a latitude/longitude box
as a small CSV plus a provenance sidecar. Layout follows the provider's format
description (GSFC_mascons_HDF5_format_RL6v02.pdf): /mascon, /time, /solution, /uncertainty.

Run with h5py supplied for this command only (it is not a project dependency):

    uv run --with h5py python scripts/extract_gsfc_mascons.py FILE.h5 --name nw_india \
        --lat 27 32 --lon 73 78 --out data/cache/earth/stories --retrieved 2026-11-15 \
        --url https://earth.gsfc.nasa.gov/sites/default/files/geo/FILE.h5
"""

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

LAND = 80  # /mascon/location code for land mascons, from the format description


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("h5", type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--lat", type=float, nargs=2, required=True, metavar=("SOUTH", "NORTH"))
    parser.add_argument("--lon", type=float, nargs=2, required=True, metavar=("WEST", "EAST"), help="degrees east, -180..180")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--retrieved", required=True, help="ISO date the global file was downloaded")
    args = parser.parse_args()
    import h5py  # noqa: PLC0415  (optional, see module docstring)

    target = args.out / f"gsfc_mascons_{args.name}.csv"
    if target.exists():
        parser.error(f"{target} exists; cached evidence is never overwritten")
    digest = hashlib.sha256(args.h5.read_bytes()).hexdigest()
    with h5py.File(args.h5, "r") as f:
        m = {k: f[f"mascon/{k}"][0] for k in ("lat_center", "lon_center", "lat_span", "lon_span", "area_km2", "location", "basin")}
        lon = (m["lon_center"] + 180) % 360 - 180
        inside = ((m["location"] == LAND) & (m["lat_center"] >= args.lat[0]) & (m["lat_center"] <= args.lat[1])
                  & (lon >= args.lon[0]) & (lon <= args.lon[1]))
        ids = np.flatnonzero(inside)
        if not len(ids):
            parser.error("no land mascon centres inside the box")
        year, doy, decimal = f["time/yyyy_doy_yrplot_middle"][:]
        cmwe = f["solution/cmwe"][ids, :]
        noise = f["uncertainty/noise_2sigma"][ids, :]
        leak_trend = f["uncertainty/leakage_trend"][ids, 0]
        leak_2s = f["uncertainty/leakage_2sigma"][ids, 0]
        days = f["time/n_ref_days_solution"][0]
    mid = pd.to_datetime(year.astype(int).astype(str), format="%Y") + pd.to_timedelta(doy - 1, unit="D")
    rows = []
    for j, mascon in enumerate(ids):
        rows.append(pd.DataFrame({
            "mid_date": mid.strftime("%Y-%m-%d"), "decimal_year": np.round(decimal, 6), "days_of_data": days.astype(int),
            "mascon_id": int(mascon) + 1,  # 1-based, as in the provider's region table
            "cmwe": cmwe[j], "noise_2sigma_cm": noise[j]}))
    args.out.mkdir(parents=True, exist_ok=True)
    pd.concat(rows).to_csv(target, index=False, float_format="%.6f")
    mascons = [{"mascon_id": int(i) + 1, "lat_center": float(m["lat_center"][i]), "lon_center": float(lon[i]),
                "lat_span": float(m["lat_span"][i]), "lon_span": float(m["lon_span"][i]),
                "area_km2": float(m["area_km2"][i]), "basin": float(m["basin"][i]),
                "leakage_trend_cm_per_year": float(leak_trend[j]), "leakage_2sigma_cm": float(leak_2s[j])}
               for j, i in enumerate(ids)]
    meta = {"name": f"gsfc_mascons_{args.name}", "dataset_card": "gsfc_grace_mascons", "source": args.url,
            "source_sha256": digest, "source_bytes": args.h5.stat().st_size, "retrieved": args.retrieved,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "product": "NASA GSFC GRACE/GRACE-FO global mascons RL06v2.0, OBP-ICE6GD", "variable": "water_storage_anomaly",
            "units": "cm equivalent water height", "baseline": "mean over 2004.0-2010.0 removed by the provider",
            "selection": {"rule": "land mascons (location code 80) whose centre lies inside the box, taken whole",
                          "south": args.lat[0], "north": args.lat[1], "west": args.lon[0], "east": args.lon[1]},
            "n_mascons": len(ids), "area_km2": float(sum(x["area_km2"] for x in mascons)), "n_solutions": int(len(mid)),
            "mascons": mascons}
    target.with_suffix(".meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
    print(f"{target}: {len(ids)} mascons, {meta['area_km2']:.0f} km2, {len(mid)} solutions")


if __name__ == "__main__":
    main()
