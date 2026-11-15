"""Fetch MODIS Terra monthly NDVI (MOD13C2 V061, 0.05 degree) over a GRACE story region's mascons.

Lists the granules in CMR and requests only the NDVI and pixel-reliability cells covering the
region's mascon footprint from the Earthdata Cloud OPeNDAP service listed in each granule's CMR
record (DAP4 CSV response). The raw grid is about 14,000 cells a month, too large to commit, so
this script keeps, for each mascon and month, the mean NDVI of reliable pixels and the counts,
and records every request address and response checksum so the cut can be re-made and checked.
Needs network and an Earthdata Login token in EDL_TOKEN.

    EDL_TOKEN=... SSL_CERT_FILE=... uv run python scripts/fetch_mod13c2_regions.py nw_india
"""

import argparse
import gzip
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/cache/earth/stories"
COLLECTION = "C2565788914-LPCLOUD"  # MOD13C2 V061, from CMR
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
OPENDAP = "https://opendap.earthdata.nasa.gov/collections/{c}/granules/{g}.dap.csv?dap4.ce={q}"
GROUP = "/MOD_Grid_monthly_CMG_VI"
NDVI, RELIABILITY = f"{GROUP}/Data_Fields/CMG_0_05_Deg_Monthly_NDVI", f"{GROUP}/Data_Fields/CMG_0_05_Deg_Monthly_pixel_reliability"
TOP_LAT, LEFT_LON, STEP = 89.975, -179.975, 0.05  # grid centres, checked against the granule's Latitude/Longitude
SCALE = 10000.0  # NDVI scale_factor in the granule DMR: physical value = stored / 10000
VALID = (-2000, 10000)  # valid_range in the granule DMR
ACCEPTED_RELIABILITY = (0, 1)  # good, marginal


def granules(start: str, end: str) -> list[tuple[str, str]]:
    found, page = [], 1
    while True:
        query = urllib.parse.urlencode({"collection_concept_id": COLLECTION, "temporal": f"{start},{end}",
                                        "page_size": 2000, "page_num": page, "sort_key": "start_date"})
        with urllib.request.urlopen(f"{CMR}?{query}", timeout=60) as response:
            entries = json.load(response)["feed"]["entry"]
        found += [(e["title"], e["time_start"][:7]) for e in entries]
        if len(entries) < 2000:
            return found
        page += 1


def index_box(footprint: dict) -> tuple[int, int, int, int]:
    i0 = int((TOP_LAT - footprint["north"]) // STEP)
    i1 = int((TOP_LAT - footprint["south"]) // STEP) + 1
    j0 = int((footprint["west"] - LEFT_LON) // STEP)
    j1 = int((footprint["east"] - LEFT_LON) // STEP) + 1
    return i0, i1, j0, j1


def parse_csv(text: str) -> dict:
    rows: dict = {NDVI: [], RELIABILITY: []}
    coords = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith("Dataset:"):
            continue
        head, *values = [part.strip() for part in line.split(",")]
        name = head.split("[")[0]
        if name in rows:
            rows[name].append([int(float(v)) for v in values])
        elif name.endswith(("Latitude", "Longitude")):
            coords[name.rsplit("/", 1)[1]] = [float(v) for v in values]
    return {"ndvi": np.array(rows[NDVI]), "reliability": np.array(rows[RELIABILITY]), **coords}


def fetch(item: tuple[str, str], box: tuple[int, int, int, int], token: str) -> dict:
    granule, month = item
    i0, i1, j0, j1 = box
    ce = ";".join([f"{GROUP}/Latitude[{i0}:{i1}]", f"{GROUP}/Longitude[{j0}:{j1}]",
                   f"{NDVI}[{i0}:{i1}][{j0}:{j1}]", f"{RELIABILITY}[{i0}:{i1}][{j0}:{j1}]"])
    url = OPENDAP.format(c=COLLECTION, g=urllib.parse.quote(granule, safe=""), q=urllib.parse.quote(ce, safe=""))
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body = response.read()
            parsed = parse_csv(body.decode())
            if parsed["ndvi"].shape != (i1 - i0 + 1, j1 - j0 + 1) or parsed["reliability"].shape != parsed["ndvi"].shape:
                raise ValueError(f"{granule}: unexpected grid shape")
            return {"granule": granule, "month": month, "url": url, "sha256": hashlib.sha256(body).hexdigest(),
                    "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **parsed}
        except Exception as exc:
            if attempt == 3:
                return {"granule": granule, "month": month, "url": url, "skipped": f"{type(exc).__name__}: {exc}"[:200]}
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def summarize(response: dict, footprints: list[dict]) -> list[dict]:
    lat, lon = np.asarray(response["Latitude"]), np.asarray(response["Longitude"])
    ndvi, rel = response["ndvi"], response["reliability"]
    keep = np.isin(rel, ACCEPTED_RELIABILITY) & (ndvi >= VALID[0]) & (ndvi <= VALID[1])
    out = []
    for f in footprints:
        inside = ((lat >= f["south"]) & (lat < f["north"]))[:, None] & ((lon >= f["west"]) & (lon < f["east"]))[None, :]
        kept = inside & keep
        out.append({"mascon_id": f["mascon_id"], "n_cells": int(inside.sum()), "n_kept": int(kept.sum()),
                    "mean_ndvi": float(ndvi[kept].mean() / SCALE) if kept.any() else None})
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tag")
    parser.add_argument("--start", default="2000-02-01T00:00:00Z")
    parser.add_argument("--end", default="2026-12-31T23:59:59Z")
    args = parser.parse_args()
    token = os.environ["EDL_TOKEN"]
    mascons = yaml.safe_load((CACHE / f"gsfc_mascons_{args.tag}.meta.yaml").read_text())
    footprints = [{"mascon_id": m["mascon_id"], "south": m["lat_center"] - m["lat_span"] / 2,
                   "north": m["lat_center"] + m["lat_span"] / 2, "west": m["lon_center"] - m["lon_span"] / 2,
                   "east": m["lon_center"] + m["lon_span"] / 2} for m in mascons["mascons"]]
    union = {"south": min(f["south"] for f in footprints), "north": max(f["north"] for f in footprints),
             "west": min(f["west"] for f in footprints), "east": max(f["east"] for f in footprints)}
    box = index_box(union)
    items = granules(args.start, args.end)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda it: fetch(it, box, token), items))
    finished = datetime.now(timezone.utc).isoformat(timespec="seconds")
    skipped = [{k: r[k] for k in ("granule", "month", "skipped")} for r in responses if "skipped" in r]
    responses = [r for r in responses if "skipped" not in r]
    bundle = {"collection": COLLECTION, "skipped": skipped, "scale": SCALE, "valid_range": list(VALID),
              "accepted_reliability": list(ACCEPTED_RELIABILITY),
              "months": {r["month"].replace("-", ""): summarize(r, footprints) for r in responses},
              "requests": [{k: r[k] for k in ("granule", "month", "url", "sha256", "retrieved_at")} for r in responses]}
    raw = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
    name = f"mod13c2_{args.tag}"
    out = CACHE / f"{name}.json.gz"
    out.write_bytes(gzip.compress(raw, mtime=0))
    meta = {
        "name": name, "dataset_card": "modis_ndvi_monthly_cmg", "product": "MOD13C2 V061",
        "source": f"https://opendap.earthdata.nasa.gov/collections/{COLLECTION}", "cmr_collection": COLLECTION,
        "retrieved": started[:10], "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "uncompressed_sha256": hashlib.sha256(raw).hexdigest(), "region": args.tag, "mascon_footprint": union,
        "grid_index_box": dict(zip(["row0", "row1", "col0", "col1"], box)), "n_months": len(responses),
        "first_month": min(bundle["months"]), "last_month": max(bundle["months"]),
        "reduction": "per mascon and month: mean NDVI of cells with reliability 0 or 1 and a value in the valid range, "
                     "with cell counts; raw grids are not kept, each response's SHA-256 is",
        "requested_period": {"start": args.start, "end": args.end},
        "request_window": {"started": started, "finished": finished},
        "acquisition": "Fetched with scripts/fetch_mod13c2_regions.py from the cloud workspace using an Earthdata Login token.",
        "skipped": bundle["skipped"],
        "note": "Real NASA data. Granules the service would not subset are listed under skipped; their months are missing, not filled."}
    (CACHE / f"{name}.meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
    print(f"{name}: {len(responses)} months, {len(skipped)} skipped {[x['month'] for x in skipped]}, {out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
