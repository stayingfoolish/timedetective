import generators as g
import numpy as np
import pandas as pd
import pytest

from timedetective.skills.detectability.detectable_trend import minimum_detectable_trend, record_length_needed
from timedetective.skills.detectability.effective_n import effective_sample_size


def test_effective_sample_size_present_and_absent():
    red = effective_sample_size(g.ar1(2000, phi=0.6, seed=1)).values
    assert red["effective_share"] == pytest.approx((1 - 0.6) / (1 + 0.6), abs=0.05)
    white = effective_sample_size(g.white_noise(2000, seed=1)).values
    assert white["effective_share"] > 0.9


def test_slope_standard_error_formula_matches_simulation():
    """The se formula behind both procedures, against the spread of fitted slopes on simulated AR(1) noise."""
    n, phi = 240, 0.5
    t = np.arange(n) / 12
    slopes = [np.polyfit(t, g.ar1(n, phi, 1.0, seed=s).to_numpy(), 1)[0] for s in range(2000)]
    predicted = np.mean([minimum_detectable_trend(g.ar1(n, phi, 1.0, seed=s)).values["slope_standard_error"] for s in range(200)])
    assert predicted == pytest.approx(np.std(slopes), rel=0.12)


def test_minimum_detectable_trend_is_alpha_plus_power_times_se():
    v = minimum_detectable_trend(g.ar1(240, 0.5, seed=2)).values
    assert v["minimum_detectable_trend"] == pytest.approx((1.959964 + 1.281552) * v["slope_standard_error"], rel=1e-5)
    assert v["slope_unit"] == "per year"


def test_longer_or_quieter_records_detect_smaller_trends():
    short = minimum_detectable_trend(g.ar1(120, 0.5, seed=3)).values["minimum_detectable_trend"]
    long = minimum_detectable_trend(g.ar1(480, 0.5, seed=3)).values["minimum_detectable_trend"]
    noisy = minimum_detectable_trend(g.ar1(240, 0.5, 3.0, seed=3)).values["minimum_detectable_trend"]
    quiet = minimum_detectable_trend(g.ar1(240, 0.5, 1.0, seed=3)).values["minimum_detectable_trend"]
    assert long < short and quiet < noisy


def test_record_length_needed_reduces_to_the_monthly_rule():
    """Monthly data, alpha=0.05, power=0.9: years = [(3.24 * sd / |trend|) * sqrt((1+phi)/(1-phi))]^(2/3)."""
    x = g.ar1(240, 0.5, seed=4)
    v = record_length_needed(x, trend=0.05).values
    expected = (3.241516 * v["noise_sd"] / 0.05 * np.sqrt((1 + v["lag1_autocorrelation"]) / (1 - v["lag1_autocorrelation"]))) ** (2 / 3)
    assert v["length_needed"] == pytest.approx(expected, rel=0.01) and v["length_unit"] == "year"


def test_long_enough_present_and_absent():
    x = g.ar1(132, 0.5, seed=5)  # eleven years of monthly data
    assert not record_length_needed(x, trend=0.01).values["long_enough"]
    assert record_length_needed(x, trend=1.0).values["long_enough"]
    assert not record_length_needed(x, trend=0.0).ok


def test_record_length_agrees_with_minimum_detectable_trend():
    x = g.ar1(240, 0.5, seed=6)
    mdt = minimum_detectable_trend(x).values
    needed = record_length_needed(x, trend=mdt["minimum_detectable_trend"]).values
    assert needed["length_needed"] == pytest.approx(mdt["span"], rel=0.01)
