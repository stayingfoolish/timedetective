"""How regular or noisy a series is."""

from itertools import permutations
from math import factorial, log2

import numpy as np
import pandas as pd

from timedetective.skills.checks import guard
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("permutation_entropy")
def permutation_entropy(x: pd.Series, order: int = 3, delay: int = 1) -> SkillResult:
    """Normalized permutation entropy (Bandt and Pompe 2002): 0 is fully regular, 1 is noise.

    Assumes a regular, gap-free series. Ties are ordered by position.
    """
    name = "permutation_entropy"
    if order < 2 or delay < 1:
        return refuse(name, "order must be at least 2 and delay at least 1", "pass valid order and delay")
    if (r := guard(name, x, 10 * factorial(order))) is not None:
        return r
    v = x.to_numpy(dtype=float)
    n_patterns = len(v) - (order - 1) * delay
    counts = dict.fromkeys(permutations(range(order)), 0)
    for i in range(n_patterns):
        counts[tuple(np.argsort(v[i : i + order * delay : delay], kind="stable"))] += 1
    probs = np.array([c for c in counts.values() if c], dtype=float) / n_patterns
    h = float(-(probs * np.log2(probs)).sum() / log2(factorial(order)))
    return SkillResult(name, {"permutation_entropy": h, "order": order, "delay": delay})
