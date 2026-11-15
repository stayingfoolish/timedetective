"""Is the change across the gap between the two satellite missions out of the ordinary for this record?"""

import numpy as np
import pandas as pd

from timedetective.packs.earth.skills.common import plain
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse
from timedetective.skills.transforms.deseasonalize import deseasonalize_harmonic

WINDOW = 6       # months averaged on each side
MIN_VALID = 4    # months that must be present in each window
MIN_PLACEBOS = 30


def _jump(values: np.ndarray, start: int, gap: int) -> float | None:
    """Mean of the WINDOW months after a gap of `gap` months starting at `start`, minus the mean of the WINDOW months before."""
    before, after = values[start - WINDOW:start], values[start + gap:start + gap + WINDOW]
    if start - WINDOW < 0 or len(after) < WINDOW or np.isfinite(before).sum() < MIN_VALID or np.isfinite(after).sum() < MIN_VALID:
        return None
    return float(np.nanmean(after) - np.nanmean(before))


@register("storage_handover")
def storage_handover(x: pd.Series, trend_values: dict, gap_start: str = "2017-07-01", gap_end: str = "2018-05-31") -> SkillResult:
    """Compare the change across the mission gap with changes across every other stretch of the same length.

    The seasonal cycle and the overall straight-line trend are removed first, so a steady
    decline does not count. The change across the gap is then ranked among the same
    measurement taken at every other position in the record (placebo gaps). If it is larger
    than 95% of them, a caution is attached: the record cannot tell a real change from an
    instrument offset there. Ranking against the record's own behaviour keeps the caution
    from firing just because the record wanders. The gap dates come from the dataset card,
    so this is one pre-declared comparison, not a search.
    """
    name = "storage_handover"
    if "conclusion" not in trend_values:
        return refuse(name, "no trend result to attach the caution to", "run the trend step first")
    cleaned = deseasonalize_harmonic(x, 12)
    if not cleaned.ok:
        return refuse(name, cleaned.refusal.failed, cleaned.refusal.would_change)
    series = cleaned.series
    values = series.to_numpy(dtype=float)
    t = np.arange(len(values), dtype=float)
    ok = np.isfinite(values)
    values = values - np.polyval(np.polyfit(t[ok], values[ok], 1), t)
    first, last = pd.Timestamp(gap_start), pd.Timestamp(gap_end)
    inside = (series.index >= first) & (series.index <= last)
    conclusion = dict(trend_values["conclusion"])
    start = int(np.argmax(inside)) if inside.any() else None
    gap = int(inside.sum())
    observed = _jump(values, start, gap) if start is not None else None
    placebos = []
    if observed is not None:
        for position in range(WINDOW, len(values) - gap - WINDOW + 1):
            if abs(position - start) < gap + WINDOW:   # skip placements that overlap the real gap
                continue
            jump = _jump(values, position, gap)
            if jump is not None:
                placebos.append(jump)
    if observed is None or len(placebos) < MIN_PLACEBOS:
        # Cannot be checked: say so and leave the caution unresolved (it then blocks "robust").
        return SkillResult(name, plain({"gap_start": gap_start, "gap_end": gap_end, "break_at_handover": None,
            "not_tested": "the record does not span the gap with enough data on both sides", "conclusion": conclusion}))
    share = (1 + sum(abs(p) >= abs(observed) for p in placebos)) / (len(placebos) + 1)
    flagged = bool(share <= 0.05)
    conclusion["evidence"] = {**conclusion["evidence"], "artifact_flag": flagged}
    if flagged:
        conclusion["limits"] = ["The change across the gap between the two satellite missions (2017-2018) is larger than "
                                "almost any other change of that length in the record; a real change and an instrument "
                                "offset cannot be told apart there.", *conclusion["limits"]]
    return SkillResult(name, plain({
        "gap_start": gap_start, "gap_end": gap_end, "gap_months": gap, "change_across_gap_cm": observed,
        "placebo_positions": len(placebos), "typical_change_cm": float(np.median(np.abs(placebos))),
        "share_of_placebos_at_least_as_large": share, "break_at_handover": flagged,
        "interpretation": "a caution, not an attribution", "conclusion": conclusion}))
