"""False-positive rate of each trend test on trend-free series with realistic autocorrelation.

Target (AGENTS.md): at or below 5%. With 500 series per cell the Monte Carlo
standard error is about 1 point, so a cell passes at or below 7.5%.

Tests marked xfail are known not to meet the target under autocorrelation.
They stay in the suite so the numbers are re-measured on every run; none of
them should be the sole basis for a "significant" claim. Do not loosen the
threshold or remove a case to make this file pass.
"""

import generators as g
import numpy as np
import pytest

import timedetective.skills  # noqa: F401
from timedetective.skills import registry

N_SERIES = 500
LIMIT = 0.075
CELLS = [(phi, n) for phi in (0.0, 0.3, 0.6) for n in (120, 240)]

MEETS_TARGET = ["mann_kendall_prewhitened"]
KNOWN_OVERSIZED = ["mann_kendall", "mann_kendall_hamed_rao", "mann_kendall_tfpw", "sens_slope", "ols_trend", "ols_trend_hac"]


def _rejects(name: str, x) -> bool | None:
    result = registry.get(name)(x)
    if not result.ok:
        return None
    v = result.values
    return bool(v["trend_detected"]) if "trend_detected" in v else not (v["ci_low"] < 0 < v["ci_high"])


def _rate(name: str, phi: float, n: int) -> float:
    series = (g.ar1(n, phi, seed=s) if phi else g.white_noise(n, seed=s) for s in range(N_SERIES))
    outcomes = [r for x in series if (r := _rejects(name, x)) is not None]
    return float(np.mean(outcomes))


def _worst(name: str) -> tuple[float, tuple[float, int]]:
    rates = {cell: _rate(name, *cell) for cell in CELLS}
    worst = max(rates, key=rates.get)
    print(f"\n{name}: " + ", ".join(f"phi={p} n={n}: {r:.3f}" for (p, n), r in rates.items()))
    return rates[worst], worst


@pytest.mark.slow
@pytest.mark.parametrize("name", MEETS_TARGET)
def test_meets_the_five_percent_target(name):
    rate, cell = _worst(name)
    assert rate <= LIMIT, f"{name} rejects {rate:.1%} of trend-free series at phi={cell[0]}, n={cell[1]}"


@pytest.mark.slow
@pytest.mark.parametrize("name", KNOWN_OVERSIZED)
@pytest.mark.xfail(strict=True, reason="rejects more than 5% of trend-free autocorrelated series")
def test_known_oversized_under_autocorrelation(name):
    rate, cell = _worst(name)
    assert rate <= LIMIT, f"{name} rejects {rate:.1%} of trend-free series at phi={cell[0]}, n={cell[1]}"


@pytest.mark.slow
def test_prewhitening_keeps_useful_power():
    """A trend of 0.01 per step in AR(1) noise (phi=0.6, n=240) should still be found most of the time."""
    hits = [
        registry.get("mann_kendall_prewhitened")(g.linear_trend(240, 0.01, phi=0.6, seed=s)).values["trend_detected"]
        for s in range(300)
    ]
    print(f"\nmann_kendall_prewhitened power at slope 0.01/step, phi=0.6, n=240: {np.mean(hits):.3f}")
    assert np.mean(hits) >= 0.5
