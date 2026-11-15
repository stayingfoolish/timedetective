import generators as g
import numpy as np
import pandas as pd
import pytest

from timedetective.skills.trend.drift import drift_test


def yearly(values):
    return pd.Series(values, index=pd.date_range("2000-01-01", periods=len(values), freq="YS"))


def test_known_answer_on_a_hand_checked_series():
    x = yearly(np.cumsum([0, 2, 0, 2, 0, 2, 0, 2, 0, 2, 0, 2, 0, 2, 0, 2]).astype(float))
    v = drift_test(x).values
    d = np.diff(x.to_numpy())
    assert v["mean_change_per_step"] == pytest.approx(d.mean()) and v["mean_change"] == pytest.approx(d.mean(), rel=1e-3)
    assert v["lag1_of_changes"] < 0
    assert v["correlation_used"] == 0.25 and v["inflation"] == pytest.approx(np.sqrt(1.25 / 0.75))
    assert v["standard_error"] == pytest.approx(d.std(ddof=1) / np.sqrt(len(d)) * np.sqrt(1.25 / 0.75))


def test_a_strong_drift_on_a_random_walk_is_found():
    rng = np.random.default_rng(1)
    v = drift_test(yearly(np.cumsum(rng.normal(-3.5, 4.0, 25)))).values
    assert v["trend_detected"] and v["direction"] == "decreasing" and v["slope_unit"] == "per year"


def test_random_walks_without_drift_are_rarely_flagged():
    """The reason this test exists: a wandering series must not be read as a trend."""
    hits = [drift_test(yearly(np.cumsum(np.random.default_rng(s).normal(0, 1, 25)))).values["trend_detected"] for s in range(400)]
    assert np.mean(hits) <= 0.06


def test_short_lived_noise_without_trend_is_almost_never_flagged():
    hits = [drift_test(yearly(g.ar1(25, 0.6, seed=s).to_numpy())).values["trend_detected"] for s in range(300)]
    assert np.mean(hits) <= 0.02


def test_persistent_changes_widen_the_standard_error():
    rng = np.random.default_rng(3)
    steps = np.zeros(40)
    for i in range(1, 40):
        steps[i] = 0.7 * steps[i - 1] + rng.normal()
    v = drift_test(yearly(np.cumsum(steps))).values
    assert v["correlation_used"] > 0.25 and v["inflation"] > np.sqrt(1.25 / 0.75)


def test_refuses_short_or_gappy_series():
    assert not drift_test(yearly(np.arange(8.0))).ok
    x = yearly(np.arange(30.0)); x.iloc[5] = np.nan
    assert not drift_test(x).ok
