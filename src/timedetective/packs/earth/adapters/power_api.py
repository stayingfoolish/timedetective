"""Bounded NASA POWER acquisition after validated distillation; immutable local cache."""

from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import yaml

from .power import load_power

ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/point"
STARTS = {"PRECTOTCORR": date(1981, 1, 1), "IMERG_PRECTOT": date(1998, 6, 1)}
MAX_BYTES = 8_000_000


def request_url(latitude: float, longitude: float, start: date, end: date, parameter: str) -> str:
    """Use only the documented endpoint; require frozen, completed historical years."""
    if parameter not in STARTS or not all(math.isfinite(v) for v in (latitude, longitude)):
        raise ValueError("invalid precipitation product or coordinates")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("coordinates outside valid range")
    if start < STARTS[parameter] or end < start or end.year >= date.today().year:
        raise ValueError("dates exceed the product coverage or completed historical-year policy")
    return ENDPOINT + "?" + urlencode({"parameters": parameter, "community": "AG",
        "longitude": longitude, "latitude": latitude, "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"), "format": "JSON", "time-standard": "UTC"})


def download(url: str) -> bytes:
    """Three bounded attempts for transient errors, not malformed/provider-denied requests."""
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": "TimeDetective/0.1 precipitation research"}), timeout=45) as response:
                if response.geturl().split("?", 1)[0] != ENDPOINT:
                    raise ValueError("unexpected API redirect")
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError("response exceeds cache size limit")
                return raw
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("unreachable retry state")


def fetch_power(*, latitude: float, longitude: float, start: date, end: date,
                parameter: str, cache_dir: Path, offline: bool = False) -> pd.Series:
    """Verify request/response coordinates, dates, checksum and units before use or reuse."""
    url = request_url(latitude, longitude, start, end, parameter)
    key = hashlib.sha256(url.encode()).hexdigest()
    entry = Path(cache_dir) / key
    matches = sorted(entry.glob("*/response.json")) if entry.exists() else []
    if matches:
        path = matches[0]  # Immutable first snapshot. Refresh requires a new cache root.
        meta = yaml.safe_load(path.with_suffix(".meta.yaml").read_text())
        if meta.get("request_url") != url:
            raise ValueError("cached request mismatch")
        validate_response(path.read_bytes(), latitude, longitude, start, end, parameter)
        return load_power(path, parameter)
    if offline:
        raise ValueError("requested precipitation data are not cached; offline mode forbids acquisition")
    raw = download(url)
    data = validate_response(raw, latitude, longitude, start, end, parameter)
    entry.mkdir(parents=True, exist_ok=True)
    snapshot = Path(tempfile.mkdtemp(prefix="snapshot-", dir=entry))
    path = snapshot / "response.json"
    meta = {"request_url": url, "retrieved": datetime.now(timezone.utc).date().isoformat(),
        "sha256": hashlib.sha256(raw).hexdigest(), "header": data["header"],
        "aggregation": "provider-native point query, daily UTC; not a regional average"}
    with path.with_suffix(".meta.yaml").open("x") as handle:
        yaml.safe_dump(meta, handle, sort_keys=False)
    with path.open("xb") as handle:
        handle.write(raw)
    return load_power(path, parameter)


def validate_response(raw: bytes, latitude: float, longitude: float, start: date,
                      end: date, parameter: str) -> dict:
    data = json.loads(raw)
    lon, lat = data["geometry"]["coordinates"][:2]
    if abs(lon - longitude) > 1e-6 or abs(lat - latitude) > 1e-6:
        raise ValueError("provider coordinates differ from the distilled request")
    if any(str(data["header"][k]) != v.strftime("%Y%m%d") for k, v in [("start", start), ("end", end)]):
        raise ValueError("provider dates differ from the distilled request")
    if data["header"]["time_standard"] != "UTC" or parameter not in data["properties"]["parameter"]:
        raise ValueError("provider returned wrong time standard or parameter")
    return data
