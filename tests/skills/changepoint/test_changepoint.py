import generators as g
import numpy as np
import pandas as pd
import pytest

from timedetective.skills.changepoint.chow import chow_test
from timedetective.skills.changepoint.cusum import cusum
from timedetective.skills.changepoint.pettitt import pettitt
from timedetective.skills.changepoint.segmented import segmented_regression, step_vs_trend


@pytest.mark.parametrize("skill", [pettitt, cusum])
def test_level_shift_present_and_absent(skill):
    present = skill(g.step_change(240, at=120, size=3, seed=1)).values
    assert present["break_detected"] and abs(present["break_position"] - 120) <= 3
    assert present["break_time"] == g.white_noise(240).index[present["break_position"]]
    assert not skill(g.white_noise(240, seed=1)).values["break_detected"]


def test_pettitt_statistic_matches_the_definition():
    x = g.step_change(60, at=25, size=1.5, seed=2)
    v = x.to_numpy()
    u = [sum(np.sign(v[j] - v[i]) for i in range(t + 1) for j in range(t + 1, 60)) for t in range(59)]
    out = pettitt(x).values
    assert out["statistic"] == pytest.approx(max(abs(a) for a in u))
    assert out["break_position"] == int(np.argmax(np.abs(u))) + 1
    assert out["p_value"] == pytest.approx(2 * np.exp(-6 * out["statistic"] ** 2 / (60**3 + 60**2)))


def test_pettitt_reference_value():
    # Change location and U statistic checked against pyhomogeneity `pettitt_test` on this
    # series and on five synthetic step series (pyhomogeneity is not a dependency; its
    # p-value is Monte Carlo, ours is the closed-form approximation).
    x = pd.Series([1.2, 0.8, 1.1, 0.9, 1.0, 1.3, 0.7, 1.0, 0.9, 1.1, 2.1, 1.9, 2.2, 2.0, 1.8, 2.3, 2.0, 1.9, 2.1, 2.2,
                   2.0, 1.8])
    out = pettitt(x).values
    assert out["break_position"] == 10 and out["statistic"] == 120.0


def test_chow_present_absent_and_refusals():
    x = g.slope_change(240, at=120, slope_after=0.05, seed=3)
    label = x.index[120]
    v = chow_test(x, label).values
    assert v["break_detected"] and v["slope_after"] > v["slope_before"]
    assert not chow_test(g.linear_trend(240, 0.02, seed=3), label).values["break_detected"]
    assert not chow_test(x, pd.Timestamp("1990-01-01")).ok
    assert not chow_test(x, x.index[2]).ok


def test_segmented_regression_present_and_absent():
    present = segmented_regression(g.slope_change(240, at=120, slope_after=0.05, seed=4)).values
    assert present["delta_bic"] > 10 and abs(present["break_position"] - 120) <= 15
    assert present["slope_after"] == pytest.approx(0.05 * 12, rel=0.2) and abs(present["slope_before"]) < 0.15
    assert segmented_regression(g.linear_trend(240, 0.02, seed=4)).values["delta_bic"] < 0


@pytest.mark.parametrize("series,expected", [
    (lambda: g.white_noise(240, seed=5), "flat"),
    (lambda: g.step_change(240, at=120, size=3, seed=5), "step"),
    (lambda: g.linear_trend(240, 0.02, seed=5), "trend"),
])
def test_step_vs_trend_picks_the_right_description(series, expected):
    assert step_vs_trend(series()).values["best_model"] == expected


def test_step_vs_trend_locates_the_step():
    v = step_vs_trend(g.step_change(240, at=120, size=3, seed=6)).values
    assert abs(v["step_position"] - 120) <= 2 and v["step_size"] == pytest.approx(3, abs=0.4)
