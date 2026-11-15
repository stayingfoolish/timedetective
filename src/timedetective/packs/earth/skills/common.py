"""Shared helpers for the season and water-storage procedures."""

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

REQUIRED = ("units", "cadence", "source", "retrieved", "variable", "product", "spatial_support", "sha256")


def plain(value: Any) -> Any:
    """Strict-JSON-safe copy: numpy scalars, timestamps and NaN become plain Python (NaN -> None)."""
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray, pd.Index)):
        return [plain(v) for v in value]
    if isinstance(value, (pd.Timestamp, date)):
        return str(value)[:10]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    return value


def metadata_problem(x: pd.Series, variable: str) -> tuple[str, str] | None:
    """The first thing wrong with a series' provenance, or None. Never repairs anything."""
    missing = [k for k in REQUIRED if k not in x.attrs]
    if missing:
        return f"missing metadata: {missing}", "load the data through an adapter that records provenance"
    if x.attrs["variable"] != variable:
        return f"expected a {variable} series, got {x.attrs['variable']}", f"supply a {variable} record"
    if not isinstance(x.index, pd.DatetimeIndex) or x.index.has_duplicates or not x.index.is_monotonic_increasing:
        return "dates are missing, duplicated or unsorted", "supply unique, ordered dates"
    try:
        date.fromisoformat(str(x.attrs["retrieved"]))
    except ValueError:
        return "invalid retrieval date", "use an ISO date"
    if not isinstance(x.attrs["spatial_support"], dict) or not x.attrs["spatial_support"].get("kind"):
        return "spatial support is not declared", "say what area the series describes"
    return None


def season_table(monthly: pd.Series, months: list[int]) -> pd.DataFrame:
    """One row per season and one column per season month (in season order); NaN where a month is missing.

    A season that wraps the new year is labelled by the year in which it starts.
    """
    first = months[0]
    frame = pd.DataFrame({"value": monthly.to_numpy(dtype=float), "month": monthly.index.month,
                          "season": monthly.index.year - (monthly.index.month < first).astype(int)})
    frame = frame[frame["month"].isin(months)]
    wide = frame.pivot(index="season", columns="month", values="value").reindex(columns=months)
    return wide


def valid_months(months: Any) -> bool:
    """Calendar months, unique, consecutive (wrapping the new year is allowed)."""
    if not isinstance(months, (list, tuple)) or not 1 <= len(months) <= 12:
        return False
    if any(not isinstance(m, int) or isinstance(m, bool) or not 1 <= m <= 12 for m in months) or len(set(months)) != len(months):
        return False
    return all((b - a) % 12 == 1 for a, b in zip(months, months[1:]))


def standing(rank: int, n: int) -> tuple[float, str]:
    """Percentile of a rank (1 = lowest) and the project's plain-language band for it."""
    percentile = 100 * (rank - 0.5) / n
    if percentile <= 10:
        band = "well below usual"
    elif percentile <= 25:
        band = "below usual"
    elif percentile < 75:
        band = "within the usual range"
    elif percentile < 90:
        band = "above usual"
    else:
        band = "well above usual"
    return percentile, band


def ordinal(k: int) -> str:
    suffix = "th" if 10 <= k % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(k % 10, "th")
    return f"{k}{suffix}"
