import generators as g
import numpy as np
import pandas as pd
import pytest

from timedetective.skills.robustness.agreement import independent_record_check, method_agreement
from timedetective.skills.robustness.fdr import fdr_correction
from timedetective.skills.robustness.period import period_sensitivity


def test_method_agreement_present_and_absent():
    assert method_agreement(g.linear_trend(240, 0.02, seed=1)).values["methods_agree"]
    spoiled = g.linear_trend(240, 0.02, sigma=0.3, seed=1)
    spoiled.iloc[:6] += 60  # a few wild early values drag least squares but not Theil-Sen
    v = method_agreement(spoiled).values
    assert not v["methods_agree"] and v["sen_slope"] > 0 > v["ols_slope"]


def test_independent_record_check_present_and_absent():
    satellite = g.linear_trend(240, 0.02, seed=2)
    station = g.linear_trend(200, 0.02, seed=3)
    assert independent_record_check(satellite, station).values["records_agree"]
    opposite = g.linear_trend(200, -0.02, seed=3)
    v = independent_record_check(satellite, opposite).values
    assert not v["records_agree"] and not v["same_sign"]


def test_period_sensitivity_present_and_absent():
    assert period_sensitivity(g.linear_trend(240, 0.02, seed=4)).values["sign_stable"]
    t = np.arange(240)
    # Flat record whose apparent rise comes entirely from a jump in its last 10%.
    late_jump = g.white_noise(240, 0.5, seed=4) + np.where(t >= 216, 4.0, 0.0) - 0.002 * t
    v = period_sensitivity(late_jump).values
    assert not v["sign_stable"] and v["share_same_sign"] < 1
    assert not period_sensitivity(g.linear_trend(240, 0.02), max_trim=0.6).ok


def test_fdr_correction_known_answer():
    p = pd.Series([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216], index=list("abcdefghij"))
    out = fdr_correction(p)
    # Benjamini-Hochberg at 0.05 on these ten values keeps the two smallest (0.001 <= 0.005, 0.008 <= 0.010).
    assert out.values["n_significant_raw"] == 5 and out.values["n_significant_fdr"] == 2
    assert out.series["a"] == pytest.approx(0.01) and out.series["b"] == pytest.approx(0.04)
    assert out.values["significant"]["a"] and not out.values["significant"]["c"]


def test_fdr_correction_on_pure_noise_and_refusals():
    rng = np.random.default_rng(5)
    p = pd.Series(rng.uniform(0, 1, 200))
    out = fdr_correction(p)
    assert out.values["n_significant_raw"] > 0 and out.values["n_significant_fdr"] == 0
    assert not fdr_correction(pd.Series([0.2])).ok
    assert not fdr_correction(pd.Series([0.2, np.nan])).ok
