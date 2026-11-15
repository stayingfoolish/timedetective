"""How often the water storage check promotes a trend-free record to "significant".

The whole path is exercised, not one test in isolation: gap-tolerant seasonal removal,
annual means, the drift test on yearly changes, the detection floor, the mission-gap
caution and the critic's rules. Target (AGENTS.md): at or below 5%. With 400 records per
cell the Monte Carlo standard error is about 1.1 points, so a cell passes at or below 7.5%.

Nulls, all with a seasonal cycle and the real record's missing months:
  short-lived noise     monthly AR(1), from none to near unit root
  wander                a random walk, alone and hidden under noise of several sizes
  rainfall              storage that only integrates rainfall departures
  smooth wander         a walk whose monthly steps are themselves persistent

Do not loosen the limit, drop a null, or widen the critic's bounds to make this pass.
"""

import json

import generators as g
import numpy as np
import pytest

from timedetective.packs.earth.stories import check_storage

N_RECORDS = 400
LIMIT = 0.075
MONTHS = 291


def _outcome(storage, rain=None) -> dict:
    finding = check_storage(storage, question="Is storage changing?", rainfall=rain)
    values = {s.node: json.loads(s.values_json) for s in finding.path}
    trend = values.get("trend", {})
    return {"promoted": finding.claim is not None and finding.claim.strength != "descriptive",
            "detected": bool(trend.get("trend_detected")),
            "second": bool(trend.get("second_method", {}).get("trend_detected")),
            "handover": bool(values.get("handover", {}).get("break_at_handover"))}


def _rates(records) -> dict:
    outcomes = [_outcome(*r) for r in records]
    return {k: float(np.mean([o[k] for o in outcomes])) for k in outcomes[0]}


def _walk(seed: int, step: float, noise: float, drift_per_year: float = 0.0):
    wander = np.random.default_rng(10_000 + seed).normal(0, step, MONTHS).cumsum()
    return g.water_storage(slope_per_year=drift_per_year, phi=0.0, sigma=noise, seed=seed) + wander


def _smooth_walk(seed: int, phi: float, step: float):
    rng = np.random.default_rng(30_000 + seed)
    e = np.zeros(MONTHS + 200)
    for i in range(1, len(e)):
        e[i] = phi * e[i - 1] + rng.normal(0, step)
    return g.water_storage(phi=0.0, sigma=0.3, seed=seed) + e[200:].cumsum()


def _report(label: str, rates: dict) -> None:
    print(f"\n{label}: promoted {rates['promoted']:.3f} | drift test fired {rates['detected']:.3f} | "
          f"prewhitened Mann-Kendall fired {rates['second']:.3f} | mission-gap caution {rates['handover']:.3f}")


@pytest.mark.slow
@pytest.mark.parametrize("phi", (0.0, 0.5, 0.8, 0.9, 0.95, 0.98, 0.995))
def test_short_lived_noise_is_rarely_promoted(phi):
    rates = _rates((g.water_storage(phi=phi, seed=s),) for s in range(N_RECORDS))
    _report(f"AR(1) phi={phi}", rates)
    assert rates["promoted"] <= LIMIT and rates["handover"] <= 0.09


@pytest.mark.slow
@pytest.mark.parametrize("step, noise", [(0.6, 0.3), (1.0, 0.1), (0.3, 1.0), (0.1, 1.0), (0.05, 1.0)])
def test_a_wandering_record_is_rarely_promoted(step, noise):
    rates = _rates((_walk(s, step, noise),) for s in range(N_RECORDS))
    _report(f"random walk step {step} + noise {noise}", rates)
    assert rates["promoted"] <= LIMIT


@pytest.mark.slow
def test_storage_that_only_integrates_rainfall_is_rarely_promoted():
    def record(seed):
        rain = g.monthly_rain(seed=20_000 + seed)
        return g.water_storage(rain=rain, response=2.0, sigma=0.5, phi=0.5, seed=seed), rain
    rates = _rates(record(s) for s in range(N_RECORDS))
    _report("rainfall-driven, no drift", rates)
    assert rates["promoted"] <= LIMIT


@pytest.mark.slow
@pytest.mark.parametrize("phi, step", [(0.5, 0.3), (0.8, 0.15), (0.9, 0.1), (0.95, 0.05)])
def test_a_smoothly_wandering_record_is_rarely_promoted(phi, step):
    rates = _rates((_smooth_walk(s, phi, step),) for s in range(N_RECORDS))
    _report(f"walk with persistent steps phi={phi}", rates)
    assert rates["promoted"] <= LIMIT


@pytest.mark.slow
def test_an_offset_between_missions_is_caught_and_never_promoted():
    rates = _rates((g.water_storage(offset_at_handover=-6.0, phi=0.5, seed=s),) for s in range(300))
    _report("6 cm offset at the mission change, no trend", rates)
    assert rates["handover"] >= 0.8 and rates["promoted"] <= LIMIT


@pytest.mark.slow
@pytest.mark.parametrize("label, make, floor", [
    ("-1.0 cm/yr in AR(1) phi 0.8 noise", lambda s: g.water_storage(slope_per_year=-1.0, phi=0.8, seed=s), 0.5),
    ("-0.5 cm/yr in AR(1) phi 0.5 noise", lambda s: g.water_storage(slope_per_year=-0.5, phi=0.5, seed=s), 0.5),
    ("-3.8 cm/yr on a random walk (step 1.3)", lambda s: _walk(s, 1.3, 0.5, -3.8), 0.5),
    ("-1.4 cm/yr on a random walk (step 0.9)", lambda s: _walk(s, 0.9, 0.5, -1.4), 0.0),
    ("-1.4 cm/yr in AR(1) phi 0.9 noise, sd 2", lambda s: g.water_storage(slope_per_year=-1.4, phi=0.9, sigma=2.0, seed=s), 0.0),
])
def test_power_is_measured(label, make, floor):
    """Power is reported for every case; only the clear ones carry a floor."""
    rates = _rates((make(s),) for s in range(200))
    _report(f"power, {label}", rates)
    assert rates["promoted"] >= floor
