"""Known effects, nulls and reference checks for experimental precipitation inference."""

import generators as g
import numpy as np
import pytest
from scipy import stats

from timedetective.packs.earth.skills.trend.precipitation import dependent_test, stationary_indices, weather_precip_inference


def test_stationary_indices_match_independent_scalar_construction():
    n, b, length, seed = 20, 199, 3, 17
    rng = np.random.default_rng(seed)
    expected = rng.integers(n, size=(b, n))
    uniform = rng.random((b, n))
    for row in range(b):
        for col in range(1, n):
            if uniform[row, col] >= 1/length:
                expected[row, col] = (expected[row, col-1]+1) % n
    np.testing.assert_array_equal(stationary_indices(n,b,length,seed), expected)


def test_seeded_trend_estimate_matches_scipy_and_detects_large_signal():
    y = g.linear_trend(n=45, slope_per_step=3, sigma=.3, seed=17).to_numpy()+100
    result = dependent_test(y, method="trend", seed=42, resamples=999)
    assert result == dependent_test(y, method="trend", seed=42, resamples=999)
    assert result["estimate"] == pytest.approx(stats.linregress(np.arange(45),y).slope)
    assert result["sen_slope"] == pytest.approx(stats.theilslopes(y).slope)
    assert result["p_value"] < .05 and result["interval"][0] > 0


def test_known_step_is_searched_and_period_contrast_is_sized():
    y = g.step_change(n=40, at=20, size=10, sigma=.2, seed=10).to_numpy()+100
    result = dependent_test(y, method="changepoint", seed=42, resamples=999)
    assert result["boundary_index"] == 20 and result["searched_boundaries"] == 25
    contrast = np.r_[np.full(20,-1/20), np.full(20,1/20)]
    period = dependent_test(y, method="period_change", contrast=contrast, seed=42, resamples=999)
    assert period["estimate"] == pytest.approx(y[20:].mean()-y[:20].mean())
    assert period["p_value"] < .05


@pytest.mark.parametrize("y", [np.ones(30), np.arange(10), np.r_[np.arange(29),np.nan], np.r_[np.arange(29),np.inf]])
def test_invalid_bootstrap_inputs_refuse(y):
    with pytest.raises(ValueError):
        dependent_test(y, method="trend", seed=1, resamples=199)


def test_incomplete_year_and_short_event_preserved_as_refusals():
    x = g.seasonal_weather()
    result = weather_precip_inference(x, method="period_change", analyses=["period_change"],
        seasons={"MAM":[3,4,5]}, baseline=[2000,2019], event=[2020,2022],seed=1,resamples=199,alpha=.05)
    assert not result.values["tests"] and result.values["subprocedure_refusals"]
    x.iloc[40] = np.nan
    result = weather_precip_inference(x, method="trend", analyses=["trend"], seasons={"annual":list(range(1,13))},
        baseline=[2000,2019],event=[2020,2022],seed=1,resamples=199,alpha=.05)
    assert not result.values["tests"] and "incomplete" in result.values["subprocedure_refusals"][0]["failed"]


def test_baseline_is_not_silently_shortened_to_product_coverage():
    x = g.seasonal_weather()
    result = weather_precip_inference(x,method="period_change",analyses=["period_change"],
        seasons={"annual":list(range(1,13))},baseline=[1981,2010],event=[2011,2024],seed=1,resamples=199,alpha=.05)
    assert not result.values["tests"]
    assert "outside complete" in result.values["subprocedure_refusals"][0]["failed"]
