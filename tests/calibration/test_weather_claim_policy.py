"""Claim-cap regression, NOT a validation of weather p-values or detection power."""

import generators as g
import numpy as np
import pytest

from timedetective.packs.earth.run import investigate


@pytest.mark.parametrize("kind", ["seasonal", "intermittent", "persistent"])
def test_uncalibrated_nulls_cannot_be_promoted(kind):
    for seed in range(12):
        x = g.seasonal_weather(seed=seed)
        rng = np.random.default_rng(seed)
        if kind == "intermittent":
            x[:] = rng.gamma(1, 20, len(x)) * (rng.random(len(x)) > .5)
        elif kind == "persistent":
            noise = np.zeros(len(x))
            for i in range(1, len(x)):
                noise[i] = .9 * noise[i-1] + rng.normal()
            x[:] = np.exp(.25 * noise) * 30
        finding = investigate(x, question="Describe the record", seasons={"MAM": [3, 4, 5]})
        assert finding.claim.strength == "descriptive"
