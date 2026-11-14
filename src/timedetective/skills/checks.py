"""Shared input guards. Each returns a refused SkillResult, or None if the input passes."""

import warnings

import numpy as np
import pandas as pd

from timedetective.skills.result import SkillResult, refuse

DAYS_PER_YEAR = 365.2425


def cadence(index: pd.Index) -> str | None:
    """Frequency string of a datetime index with a fixed cadence (e.g. "MS"), else None."""
    if not isinstance(index, pd.DatetimeIndex) or len(index) < 3:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            freq = pd.infer_freq(index)
        except ValueError:
            return None
    return getattr(freq, "freqstr", freq)


def is_regular(x: pd.Series) -> bool:
    """True if the index is not datetime, or is datetime with an inferable fixed cadence."""
    if not isinstance(x.index, pd.DatetimeIndex):
        return True
    return cadence(x.index) is not None


def guard(
    procedure: str,
    x: pd.Series,
    min_n: int,
    *,
    allow_missing: bool = False,
    need_regular: bool = True,
    allow_constant: bool = False,
) -> SkillResult | None:
    """Refuse on non-numeric input, missing values, irregular spacing or a too-short record."""
    if not isinstance(x, pd.Series) or not pd.api.types.is_numeric_dtype(x):
        return refuse(procedure, "input is not a numeric pandas Series", "pass a numeric Series")
    if need_regular and not is_regular(x):
        return refuse(
            procedure,
            "the series is irregularly spaced",
            "run `regularize` to put it on a fixed cadence",
        )
    n_missing = int(x.isna().sum())
    if n_missing and not allow_missing:
        return refuse(
            procedure,
            f"the series has {n_missing} missing values",
            "run `gap_fill`, or choose a procedure that tolerates gaps",
        )
    n = int(x.notna().sum())
    if n < min_n:
        return refuse(
            procedure,
            f"only {n} observations; this procedure needs at least {min_n}",
            "use a longer record or a coarser question",
        )
    if n and not allow_constant and float(np.nanstd(x.to_numpy(dtype=float))) == 0.0:
        return refuse(procedure, "the series is constant", "nothing to analyse in a constant series")
    return None


def time_axis(x: pd.Series) -> tuple[np.ndarray, str]:
    """Time as a float array and its unit: decimal years for a datetime index, else steps."""
    if isinstance(x.index, pd.DatetimeIndex):
        days = (x.index - x.index[0]) / pd.Timedelta(days=1)
        return np.asarray(days, dtype=float) / DAYS_PER_YEAR, "year"
    return np.arange(len(x), dtype=float), "step"


def steps_per_unit(x: pd.Series) -> float:
    """Observations per time unit of `time_axis` (per year for datetime, else 1)."""
    t, unit = time_axis(x)
    if unit == "step" or len(t) < 2:
        return 1.0
    return float((len(t) - 1) / (t[-1] - t[0]))


def phase(x: pd.Series, period: int) -> np.ndarray:
    """Position within the seasonal cycle: calendar month for monthly data with period 12, else index mod period."""
    if isinstance(x.index, pd.DatetimeIndex) and period == 12:
        return x.index.month.to_numpy() - 1
    return np.arange(len(x)) % period
