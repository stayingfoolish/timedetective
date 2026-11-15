"""Where does the level of a series shift? Several shifts allowed."""

import numpy as np
import pandas as pd
import ruptures as rpt

from timedetective.skills.checks import guard
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("pelt")
def pelt(x: pd.Series, min_segment: int = 5, penalty: float | None = None) -> SkillResult:
    """Splits the series into stretches of constant level, with as many changes as the penalty allows.

    Uses `ruptures.Pelt` with the least-squares cost and every position as a candidate.
    Each extra change must lower the squared error by more than `penalty`; the default is
    2 * sigma^2 * log(n), a BIC-style choice, with sigma estimated from first differences
    (median absolute deviation, so that the shifts themselves do not inflate it).

    Assumes independent noise around a level that is constant between changes. Under
    autocorrelated noise it finds too many changes, and it cuts a steady trend into steps,
    so pair it with `step_vs_trend` before calling a change a shift in level. It returns
    locations and sizes, not a significance level.
    """
    name = "pelt"
    if min_segment < 2:
        return refuse(name, f"min_segment must be at least 2, got {min_segment}", "pass a longer minimum segment")
    if (r := guard(name, x, 3 * min_segment)) is not None:
        return r
    values = x.to_numpy(dtype=float)
    n = len(values)
    differences = np.diff(values)
    sigma = float(1.4826 * np.median(np.abs(differences - np.median(differences))) / np.sqrt(2))
    if penalty is None:
        if sigma <= 0:
            return refuse(name, "the noise level could not be estimated (more than half the steps are identical)",
                          "pass an explicit penalty")
        penalty = 2 * sigma**2 * np.log(n)
    if penalty <= 0:
        return refuse(name, f"penalty must be positive, got {penalty}", "pass a positive penalty")
    ends = rpt.Pelt(model="l2", min_size=min_segment, jump=1).fit(values).predict(pen=float(penalty))
    starts = [0, *ends[:-1]]
    segments = [{"start": x.index[a], "end": x.index[b - 1], "n": b - a, "mean": float(values[a:b].mean())}
                for a, b in zip(starts, ends)]
    means = [s["mean"] for s in segments]
    return SkillResult(name, {
        "n_changes": len(ends) - 1,
        "change_positions": [int(e) for e in ends[:-1]],
        "change_times": [x.index[e] for e in ends[:-1]],
        "shifts": [float(b - a) for a, b in zip(means, means[1:])],
        "segments": segments,
        "penalty": float(penalty), "noise_sd": sigma, "min_segment": min_segment,
        "cost": "least squares (piecewise-constant level)", "search": "PELT, exact, every position a candidate",
    })
