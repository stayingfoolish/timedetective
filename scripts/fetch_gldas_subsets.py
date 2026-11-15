"""Fetch GLDAS Noah monthly (v2.1) land-storage fields over a GRACE story region, for subtraction.

Reads the region's mascon footprint from its cached `.meta.yaml`, lists the GLDAS granules in
CMR, and requests only the grid cells covering that footprint from the Earthdata Cloud OPeNDAP
service listed in each granule's CMR record (ASCII response, DAP2 constraint). Writes one gzip
JSON bundle and a `.meta.yaml` sidecar with checksums. Not part of the library: needs network
and an Earthdata Login token in the environment variable EDL_TOKEN.

    EDL_TOKEN=... SSL_CERT_FILE=... uv run python scripts/fetch_gldas_subsets.py nw_india
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

import yaml

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/cache/earth/stories"
COLLECTION = "C1342986036-GES_DISC"  # GLDAS_NOAH025_M v2.1, from CMR
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
OPENDAP = "https://opendap.earthdata.nasa.gov/collections/{c}/granules/{g}.ascii?{q}"
VARIABLES = ["SoilMoi0_10cm_inst", "SoilMoi10_40cm_inst", "SoilMoi40_100cm_inst", "SoilMoi100_200cm_inst",
             "SWE_inst", "CanopInt_inst"]
FIRST_LAT, FIRST_LON, STEP = -59.875, -179.875, 0.25  # grid centres, from the granule's DMR


def granules(start: str, end: str) -> list[str]:
    names, page = [], 1
    while True:
        query = urllib.parse.urlencode({"collection_concept_id": COLLECTION, "temporal": f"{start},{end}",
                                        "page_size": 2000, "page_num": page, "sort_key": "start_date"})
        with urllib.request.urlopen(f"{CMR}?{query}", timeout=60) as response:
            entries = json.load(response)["feed"]["entry"]
        names += [e["title"] for e in entries]
        if len(entries) < 2000:
            return names
        page += 1


def index_box(footprint: dict) -> tuple[int, int, int, int]:
    """Grid indices of every cell whose centre lies inside the footprint, padded by one cell."""
    i0 = int((footprint["south"] - FIRST_LAT) // STEP)
    i1 = int((footprint["north"] - FIRST_LAT) // STEP) + 1
    j0 = int((footprint["west"] - FIRST_LON) // STEP)
    j1 = int((footprint["east"] - FIRST_LON) // STEP) + 1
    return i0, i1, j0, j1


def parse_ascii(text: str) -> dict:
    """Read Hyrax DAP2 ASCII: coordinate rows, then one row per (variable, lat)."""
    out: dict = {"grids": {}}
    for line in text.splitlines():
        if not line.strip() or line.startswith("Dataset:"):
            continue
        head, *values = [part.strip() for part in line.split(",")]
        if head in ("lat", "lon", "time"):
            out[head] = [float(v) for v in values]
        elif "[" in head:
            name = head.split(".")[0]
            out["grids"].setdefault(name, []).append([None if float(v) <= -9000 else float(v) for v in values])
    return out


def fetch(granule: str, box: tuple[int, int, int, int], token: str) -> dict:
    i0, i1, j0, j1 = box
    constraint = ",".join([f"lat[{i0}:{i1}]", f"lon[{j0}:{j1}]", "time"] +
                          [f"{v}[0][{i0}:{i1}][{j0}:{j1}]" for v in VARIABLES])
    url = OPENDAP.format(c=COLLECTION, g=urllib.parse.quote(granule, safe=""),
                         q=urllib.parse.quote(constraint, safe=","))
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read()
            parsed = parse_ascii(body.decode())
            if set(parsed["grids"]) != set(VARIABLES):
                raise ValueError(f"{granule}: response lacks some variables")
            return {"granule": granule, "url": url, "sha256": hashlib.sha256(body).hexdigest(),
                    "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **parsed}
        except Exception:  # network hiccups are retried; a persistent failure stops the run
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tag", help="story region tag, e.g. nw_india or high_plains")
    parser.add_argument("--start", default="2002-01-01T00:00:00Z")
    parser.add_argument("--end", default="2026-12-31T23:59:59Z")
    args = parser.parse_args()
    token = os.environ["EDL_TOKEN"]
    mascons = yaml.safe_load((CACHE / f"gsfc_mascons_{args.tag}.meta.yaml").read_text())
    spans = [(m["lat_center"] - m["lat_span"] / 2, m["lat_center"] + m["lat_span"] / 2,
              m["lon_center"] - m["lon_span"] / 2, m["lon_center"] + m["lon_span"] / 2) for m in mascons["mascons"]]
    footprint = {"south": min(s[0] for s in spans), "north": max(s[1] for s in spans),
                 "west": min(s[2] for s in spans), "east": max(s[3] for s in spans)}
    box = index_box(footprint)
    names = granules(args.start, args.end)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda g: fetch(g, box, token), names))
    finished = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lat, lon = responses[0]["lat"], responses[0]["lon"]
    if any(r["lat"] != lat or r["lon"] != lon for r in responses):
        raise ValueError("responses cover different grids")
    bundle = {"collection": COLLECTION, "variables": VARIABLES, "units": "kg m-2", "lat": lat, "lon": lon,
              "months": {r["granule"].split(".A")[1][:6]: r["grids"] for r in responses},
              "requests": [{k: r[k] for k in ("granule", "url", "sha256", "retrieved_at")} for r in responses]}
    raw = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
    name = f"gldas_noah025_m_{args.tag}"
    out = CACHE / f"{name}.json.gz"
    out.write_bytes(gzip.compress(raw, mtime=0))
    meta = {
        "name": name, "dataset_card": "gldas_noah_monthly", "product": "GLDAS_NOAH025_M v2.1",
        "source": "https://opendap.earthdata.nasa.gov/collections/C1342986036-GES_DISC",
        "cmr_collection": COLLECTION, "retrieved": started[:10], "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "uncompressed_sha256": hashlib.sha256(raw).hexdigest(), "variables": VARIABLES, "units": "kg m-2 (= mm of water)",
        "region": args.tag, "mascon_footprint": footprint, "grid_index_box": dict(zip(["lat0", "lat1", "lon0", "lon1"], box)),
        "n_months": len(responses), "first_month": min(bundle["months"]), "last_month": max(bundle["months"]),
        "request_window": {"started": started, "finished": finished},
        "acquisition": "Fetched with scripts/fetch_gldas_subsets.py from the cloud workspace using an Earthdata Login token.",
        "citation": "Beaudoing, H. and M. Rodell, NASA/GSFC/HSL (2020), GLDAS Noah Land Surface Model L4 monthly 0.25 x 0.25 "
                    "degree V2.1, Greenbelt, Maryland, USA, Goddard Earth Sciences Data and Information Services Center "
                    "(GES DISC), doi:10.5067/SXAVCZFAQLNO",
        "note": "Real NASA model output; used to subtract modelled soil moisture, snow and canopy water from GRACE total storage."}
    (CACHE / f"{name}.meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
    print(f"{name}: {len(responses)} months, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
