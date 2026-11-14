import generators as g
import numpy as np
import pandas as pd
import pymannkendall as mk
import pytest

from timedetective.skills.trend.bootstrap import block_bootstrap_slope
from timedetective.skills.trend.linearity import linearity_check
from timedetective.skills.trend.mann_kendall import (
    mann_kendall,
    mann_kendall_hamed_rao,
    mann_kendall_prewhitened,
    mann_kendall_tfpw,
    seasonal_kendall,
)
from timedetective.skills.trend.ols import ols_trend, ols_trend_hac
from timedetective.skills.trend.sens_slope import sens_slope

TRUE_SLOPE = 0.02 * 12  # generator slope per step, monthly data, reported per year


@pytest.mark.parametrize("skill", [ols_trend, ols_trend_hac, sens_slope])
def test_slope_estimators_present_and_absent(skill):
    present = skill(g.linear_trend(240, 0.02, seed=1)).values
    assert present["slope_unit"] == "per year"
    assert present["ci_low"] < TRUE_SLOPE < present["ci_high"] and present["ci_low"] > 0
    absent = skill(g.white_noise(240, seed=1)).values
    assert absent["ci_low"] < 0 < absent["ci_high"]


def test_slope_is_per_step_without_a_datetime_index():
    x = pd.Series(g.linear_trend(240, 0.02, seed=1).to_numpy())
    v = ols_trend(x).values
    assert v["slope_unit"] == "per step" and v["slope"] == pytest.approx(0.02, abs=0.005)


@pytest.mark.parametrize("skill", [mann_kendall, mann_kendall_hamed_rao, mann_kendall_prewhitened, mann_kendall_tfpw])
def test_mann_kendall_family_present_and_absent(skill):
    present = skill(g.linear_trend(240, 0.02, seed=2)).values
    assert present["trend_detected"] and present["direction"] == "increasing"
    assert present["slope"] == pytest.approx(TRUE_SLOPE, rel=0.25)
    absent = skill(g.white_noise(240, seed=2)).values
    assert not absent["trend_detected"] and absent["direction"] == "no trend"


def test_mann_kendall_matches_the_library_and_handles_ties():
    x = g.linear_trend(120, 0.02, seed=3).round(0)  # rounding creates many ties
    ours, ref = mann_kendall(x).values, mk.original_test(x.to_numpy())
    assert ours["p_value"] == pytest.approx(ref.p) and ours["s"] == ref.s and ours["tau"] == pytest.approx(ref.Tau)


def test_autocorrelation_inflates_plain_mann_kendall_and_prewhitening_corrects_it():
    series = [g.ar1(240, phi=0.7, seed=s) for s in range(300)]
    plain = np.mean([mann_kendall(x).values["trend_detected"] for x in series])
    hamed = np.mean([r.values["trend_detected"] for x in series if (r := mann_kendall_hamed_rao(x)).ok])
    prewhitened = np.mean([mann_kendall_prewhitened(x).values["trend_detected"] for x in series])
    assert plain > 0.25  # the uncorrected test rejects far too often on trend-free red noise
    assert hamed < plain
    assert prewhitened < 0.09  # full measurement against the 5% target is in tests/calibration


def test_seasonal_kendall_present_and_absent():
    present = seasonal_kendall(g.seasonal(240, amplitude=5, slope_per_step=0.02, seed=4), 12).values
    assert present["trend_detected"] and present["slope"] == pytest.approx(TRUE_SLOPE, rel=0.25)
    assert present["slope_unit"] == "per cycle"
    assert not seasonal_kendall(g.seasonal(240, amplitude=5, seed=4), 12).values["trend_detected"]


def test_block_bootstrap_is_seeded_and_wider_under_autocorrelation():
    x = g.linear_trend(240, 0.02, phi=0.7, seed=5)
    a = block_bootstrap_slope(x, seed=11, block_length=24).values
    b = block_bootstrap_slope(x, seed=11, block_length=24).values
    assert a == b
    naive = ols_trend(x).values
    assert (a["ci_high"] - a["ci_low"]) > (naive["ci_high"] - naive["ci_low"])
    covered = [
        v["ci_low"] < 0 < v["ci_high"]
        for k in range(100)
        if (v := block_bootstrap_slope(g.white_noise(120, seed=k), seed=k, n_boot=400).values)
    ]
    assert np.mean(covered) >= 0.88  # nominal 95% interval on trend-free white noise


def test_hac_interval_is_wider_than_ols_under_autocorrelation():
    x = g.linear_trend(240, 0.02, phi=0.7, seed=6)
    ols, hac = ols_trend(x).values, ols_trend_hac(x).values
    assert ols["slope"] == pytest.approx(hac["slope"])
    assert (hac["ci_high"] - hac["ci_low"]) > (ols["ci_high"] - ols["ci_low"])


def test_ols_returns_residuals():
    out = ols_trend(g.linear_trend(240, 0.02, seed=7))
    assert len(out.series) == 240 and abs(out.series.mean()) < 1e-8


def test_linearity_check_present_and_absent():
    t = np.arange(240)
    curved = g.white_noise(240, seed=8) + 0.0005 * (t - 120) ** 2
    assert linearity_check(curved).values["curved"]
    assert not linearity_check(g.linear_trend(240, 0.02, seed=8)).values["curved"]
