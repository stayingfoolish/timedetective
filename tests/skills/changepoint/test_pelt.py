import generators as g
import numpy as np
import pandas as pd
import pytest

from timedetective.skills.changepoint.pelt import pelt


def test_finds_one_step_where_it_is():
    v = pelt(g.step_change(240, at=120, size=3.0, seed=1)).values
    assert v["n_changes"] == 1 and abs(v["change_positions"][0] - 120) <= 3
    assert v["shifts"][0] == pytest.approx(3.0, abs=0.4)
    assert [s["n"] for s in v["segments"]] == [v["change_positions"][0], 240 - v["change_positions"][0]]


def test_finds_two_steps():
    x = g.white_noise(300, 1.0, seed=2)
    x.iloc[100:] += 4.0
    x.iloc[200:] -= 6.0
    v = pelt(x).values
    assert v["n_changes"] == 2
    assert all(abs(a - b) <= 3 for a, b in zip(v["change_positions"], (100, 200)))
    assert np.sign(v["shifts"]).tolist() == [1.0, -1.0]


def test_noise_with_no_change_is_rarely_split():
    found = [pelt(g.white_noise(200, seed=s)).values["n_changes"] > 0 for s in range(100)]
    assert np.mean(found) <= 0.10


def test_a_larger_penalty_allows_fewer_changes():
    x = g.step_change(240, at=120, size=3.0, seed=1)
    assert pelt(x, penalty=1e6).values["n_changes"] == 0
    assert not pelt(x, penalty=-1.0).ok


def test_a_steady_trend_is_cut_into_steps():
    """Documented limit: the model is a constant level between changes, so a ramp becomes a staircase.

    This is why a change found here is checked with `step_vs_trend` before it is called a shift in level.
    """
    found = [pelt(g.linear_trend(120, 0.03, seed=s)).values["n_changes"] >= 1 for s in range(30)]
    assert np.mean(found) >= 0.9


def test_autocorrelated_noise_is_over_split():
    """Documented limit: with persistent noise and no change at all, almost every series is split."""
    found = [pelt(g.ar1(120, 0.6, seed=s)).values["n_changes"] > 0 for s in range(40)]
    assert np.mean(found) >= 0.9


def test_refuses_what_it_cannot_handle():
    assert not pelt(g.white_noise(10)).ok
    assert not pelt(g.white_noise(100), min_segment=1).ok
    assert not pelt(pd.Series(np.ones(60), index=g.white_noise(60).index)).ok
    x = g.white_noise(100)
    x.iloc[10] = np.nan
    assert not pelt(x).ok
