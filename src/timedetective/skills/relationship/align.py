"""Shared alignment guard for two-series procedures."""

import pandas as pd

from timedetective.skills.checks import guard
from timedetective.skills.result import SkillResult, refuse


def guard_pair(procedure: str, x: pd.Series, y: pd.Series, min_n: int) -> SkillResult | None:
    """Refuse unless both series pass `guard` and share an identical index."""
    for s in (x, y):
        if (r := guard(procedure, s, min_n)) is not None:
            return r
    if not x.index.equals(y.index):
        return refuse(
            procedure,
            "the two series do not share the same index",
            "regularize both to one cadence and trim them to their common period",
        )
    return None
