"""Many tests at once: how many of the rejections are believable?"""

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("fdr_correction")
def fdr_correction(p_values: pd.Series, alpha: float = 0.05) -> SkillResult:
    """Benjamini-Hochberg control of the false discovery rate across a family of tests.

    Input is one p-value per region or grid cell. Assumes the tests are
    independent or positively dependent. Returns adjusted p-values as `series`.
    """
    name = "fdr_correction"
    if not isinstance(p_values, pd.Series) or len(p_values) < 2:
        return refuse(name, "need a Series of two or more p-values", "pass one p-value per region")
    p = p_values.to_numpy(dtype=float)
    if np.isnan(p).any() or (p < 0).any() or (p > 1).any():
        return refuse(name, "p-values must be between 0 and 1 with none missing", "drop regions whose test was refused")
    rejected, adjusted, *_ = multipletests(p, alpha=alpha, method="fdr_bh")
    return SkillResult(
        name,
        {
            "n_tests": len(p),
            "n_significant_raw": int((p < alpha).sum()),
            "n_significant_fdr": int(rejected.sum()),
            "significant": dict(zip(p_values.index, rejected.tolist())),
            "alpha": alpha,
        },
        series=pd.Series(adjusted, index=p_values.index, name="p_adjusted"),
    )
