"""Outlier screen. Flags points; never removes them."""

import numpy as np
import pandas as pd

from timedetective.skills.checks import guard
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse

MAD_TO_SD = 1.4826  # scales the median absolute deviation to a normal SD


@register("outlier_screen")
def outlier_screen(x: pd.Series, window: int = 13, n_sigmas: float = 3.0) -> SkillResult:
    """Hampel identifier: flags points more than `n_sigmas` scaled MADs from the rolling median.

    Assumes a regular series whose level changes slowly relative to `window`.
    Short windows estimate the spread poorly and over-flag; points near the
    ends are judged against the nearest full window.
    """
    name = "outlier_screen"
    if window < 3 or window % 2 == 0:
        return refuse(name, f"window must be odd and at least 3, got {window}", "pass an odd window")
    if (r := guard(name, x, window)) is not None:
        return r
    roll = x.rolling(window, center=True)
    med = roll.median().bfill().ffill()  # points near the ends use the nearest full window
    mad = roll.apply(lambda w: np.median(np.abs(w - np.median(w))), raw=True).bfill().ffill()
    flagged = ((x - med).abs() > n_sigmas * MAD_TO_SD * mad) & (mad > 0)
    idx = np.flatnonzero(flagged.to_numpy())
    return SkillResult(name, {
        "n_outliers": len(idx),
        "outlier_share": len(idx) / len(x),
        "outlier_positions": idx.tolist(),
        "outlier_index": [x.index[i] for i in idx],
        "has_outliers": bool(len(idx)),
    })
