"""Archive an already downloaded, unmodified POWER response and its provenance.

The URL and retrieval date must describe the actual download, not a new retrieval.
No network access; never replaces an existing cache entry.
"""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--url", required=True)
    parser.add_argument("--retrieved", required=True)
    args = parser.parse_args()
    raw = args.raw.read_bytes()
    data = json.loads(raw)
    url = urlparse(args.url)
    if url.scheme != "https" or url.hostname != "power.larc.nasa.gov" or url.path != "/api/temporal/daily/point":
        parser.error("expected the documented NASA POWER daily point endpoint")
    query = parse_qs(url.query)
    lon, lat = data["geometry"]["coordinates"][:2]
    if float(query["longitude"][0]) != lon or float(query["latitude"][0]) != lat:
        parser.error("request coordinates differ from response")
    if any(query[k][0] != data["header"][k] for k in ["start", "end"]):
        parser.error("request dates differ from response")
    sidecar = args.target.with_suffix(".meta.yaml")
    if args.target.exists() or sidecar.exists():
        parser.error("cache entry exists; choose a new name")
    meta = {"dataset": "nasa_power_daily", "request_url": args.url, "retrieved": args.retrieved,
            "sha256": hashlib.sha256(raw).hexdigest(), "region": {"kind": "point", "latitude": lat, "longitude": lon},
            "aggregation": "provider-native point query; daily UTC; no regional aggregation",
            "parameters": list(data["properties"]["parameter"]), "header": data["header"],
            "note": "Real NASA response; synthetic data are used only in separate calibration and known-answer tests."}
    args.target.parent.mkdir(parents=True, exist_ok=True)
    with args.target.open("xb") as handle:
        handle.write(raw)
    with sidecar.open("x") as handle:
        yaml.safe_dump(meta, handle, sort_keys=False)
    print(json.dumps({"sha256": meta["sha256"], "bytes": len(raw), "parameters": meta["parameters"]}))


if __name__ == "__main__":
    main()
