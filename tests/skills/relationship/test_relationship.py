import generators as g
import numpy as np
import pandas as pd
import pytest

from timedetective.skills.relationship.cointegration import cointegration_engle_granger, johansen
from timedetective.skills.relationship.cross_correlation import lagged_cross_correlation, partial_correlation
from timedetective.skills.relationship.decoupling import decoupling_test, rolling_regression
from timedetective.skills.relationship.slope_difference import slope_difference


def test_lagged_cross_correlation_finds_the_lead():
    x, y = g.coupled_pair(300, lag=3, seed=1)
    v = lagged_cross_correlation(x, y, max_lag=8).values
    assert v["best_lag"] == 3 and v["correlated"] and v["correlation"] > 0.6
    swapped = lagged_cross_correlation(y, x, max_lag=8).values
    assert swapped["best_lag"] == -3


def test_lagged_cross_correlation_absent():
    a, b = g.white_noise(300, seed=1), g.white_noise(300, seed=2)
    assert abs(lagged_cross_correlation(a, b, max_lag=0).values["correlation"]) < 0.15
    assert not lagged_cross_correlation(a, b, max_lag=0).values["correlated"]


def test_pair_procedures_refuse_misaligned_series():
    a = g.white_noise(300, seed=1)
    b = g.white_noise(300, seed=2).iloc[5:]
    for result in (lagged_cross_correlation(a, b), decoupling_test(a, b), slope_difference(a, b)):
        assert not result.ok and "same index" in result.refusal.failed


def test_partial_correlation_removes_a_shared_driver():
    z = g.ar1(400, 0.5, seed=3)
    x = z + g.white_noise(400, 0.5, seed=4)
    y = z + g.white_noise(400, 0.5, seed=5)
    v = partial_correlation(x, y, z).values
    assert v["raw_correlation"] > 0.6 and abs(v["partial_correlation"]) < 0.12 and not v["correlated"]
    direct = partial_correlation(x, x + g.white_noise(400, 0.5, seed=6), z).values
    assert direct["correlated"] and direct["partial_correlation"] > 0.5


def test_decoupling_present_and_absent():
    x, y = g.decoupling_pair(240, at=120, drift_after=-0.05, seed=7)
    v = decoupling_test(x, y).values
    assert v["decoupled"] and v["residual_shift"] < 0 and 100 <= v["break_position"] <= 200
    x2, y2 = g.decoupling_pair(240, at=120, drift_after=0.0, seed=7)
    assert not decoupling_test(x2, y2).values["decoupled"]


def test_rolling_regression_shows_a_changing_slope():
    x = g.ar1(300, 0.5, seed=8)
    beta = np.where(np.arange(300) < 150, 1.0, 0.2)
    y = pd.Series(beta * x.to_numpy(), index=x.index) + g.white_noise(300, 0.2, seed=9)
    out = rolling_regression(x, y, window=40)
    assert out.series.iloc[:39].isna().all()
    assert out.series.iloc[60:140].mean() == pytest.approx(1.0, abs=0.15)
    assert out.series.iloc[200:].mean() == pytest.approx(0.2, abs=0.15)
    stable = rolling_regression(x, x + g.white_noise(300, 0.2, seed=9), window=40)
    assert stable.values["slope_range"] < out.values["slope_range"] / 2


def test_cointegration_present_and_absent():
    x, y = g.cointegrated_pair(300, seed=10)
    assert cointegration_engle_granger(x, y).values["cointegrated"]
    a, b = g.random_walk(300, seed=11), g.random_walk(300, seed=12)
    assert not cointegration_engle_granger(a, b).values["cointegrated"]


def test_johansen_rank():
    def ranks(make, **kwargs):
        return [johansen(make(s), **kwargs).values["cointegration_rank"] for s in range(100, 160)]

    def linked(s):
        x, y = g.cointegrated_pair(400, seed=s)
        return pd.DataFrame({"x": x, "y": y})

    def independent(s):
        return pd.DataFrame({"a": g.random_walk(400, seed=s), "b": g.random_walk(400, seed=s + 1000)})

    assert np.mean(np.array(ranks(linked)) == 1) >= 0.9
    assert np.mean(np.array(ranks(independent)) == 0) >= 0.9
    # Fitting a constant to driftless series over-rejects: full rank far more often than 5%.
    assert np.mean(np.array(ranks(linked, det_order=0)) == 2) > 0.15
    full = johansen(pd.DataFrame({"a": g.white_noise(400, seed=1), "b": g.white_noise(400, seed=2)})).values
    assert full["full_rank"] and not full["cointegrated"]
    assert not johansen(g.white_noise(400)).ok


def test_slope_difference_present_absent_and_opposite_sign():
    shared = g.ar1(240, 0.6, 1.0, seed=16)  # weather both neighbourhoods share
    t = np.arange(240)
    fast = shared + 0.03 * t + g.white_noise(240, 0.3, seed=17)
    slow = shared + 0.01 * t + g.white_noise(240, 0.3, seed=18)
    v = slope_difference(fast, slow).values
    assert v["slopes_differ"] and v["slope_difference"] == pytest.approx(0.02 * 12, rel=0.2) and not v["opposite_sign"]
    same = slope_difference(fast, shared + 0.03 * t + g.white_noise(240, 0.3, seed=19)).values
    assert not same["slopes_differ"]
    down = shared - 0.02 * t
    assert slope_difference(fast, down).values["opposite_sign"]
