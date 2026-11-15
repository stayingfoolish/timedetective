import generators as g
import numpy as np
import pandas as pd
import pytest

from timedetective.skills.diagnostics.autocorrelation import autocorrelation
from timedetective.skills.diagnostics.entropy import permutation_entropy
from timedetective.skills.diagnostics.outliers import outlier_screen
from timedetective.skills.diagnostics.record import gap_audit, record_summary
from timedetective.skills.diagnostics.residuals import residual_diagnostics
from timedetective.skills.diagnostics.seasonality import seasonal_kruskal, seasonality_acf, seasonality_periodogram
from timedetective.skills.diagnostics.stationarity import stationarity
from timedetective.skills.diagnostics.strength import component_strength


def test_record_summary_and_gap_audit():
    x = g.with_gaps(g.white_noise(120), [10, 11, 12, 40])
    s = record_summary(x).values
    assert s["n"] == 120 and s["n_missing"] == 4 and s["regular"] and s["cadence"] == "MS"
    assert s["span_unit"] == "year" and s["span"] == pytest.approx(119 / 12, abs=0.01)
    a = gap_audit(x).values
    assert a["n_gaps"] == 2 and a["longest_gap"] == 3 and a["gap_lengths"] == [3, 1]
    assert gap_audit(g.white_noise(120)).values["has_gaps"] is False


def test_record_summary_flags_irregular_spacing():
    idx = pd.to_datetime(["2020-01-01", "2020-01-03", "2020-01-04", "2020-02-20"])
    assert record_summary(pd.Series([1.0, 2, 3, 4], index=idx)).values["regular"] is False
    assert not autocorrelation(pd.Series(np.arange(4.0), index=idx)).ok


def test_outlier_screen_present_and_absent():
    x = g.white_noise(200, seed=1)
    spiked = x.copy()
    spiked.iloc[100] += 15
    assert 100 in outlier_screen(spiked).values["outlier_positions"]
    assert outlier_screen(spiked, n_sigmas=5).values["outlier_positions"] == [100]
    assert outlier_screen(x, n_sigmas=5).values["n_outliers"] == 0


def test_autocorrelation_present_and_absent():
    present = autocorrelation(g.ar1(300, phi=0.7, seed=2)).values
    assert present["autocorrelated"] and present["lag1_autocorrelation"] == pytest.approx(0.7, abs=0.12)
    assert not autocorrelation(g.white_noise(300, seed=2)).values["autocorrelated"]


def test_stationarity_classifies_noise_and_random_walk():
    assert stationarity(g.white_noise(300, seed=3)).values["stationarity"] == "stationary"
    assert stationarity(g.random_walk(300, seed=3)).values["stationarity"] == "unit_root"
    # A deterministic trend is stationary around a trend, not around a level.
    trend = g.linear_trend(300, slope_per_step=0.05, seed=3)
    assert stationarity(trend, regression="ct").values["stationarity"] == "stationary"
    assert not stationarity(trend, regression="bad").ok


def test_seasonality_detectors_present_and_absent():
    s, w = g.seasonal(240, seed=4), g.white_noise(240, seed=4)
    assert seasonality_acf(s).values["period"] == 12
    assert seasonality_acf(w).values["seasonal"] is False
    false_alarms = sum(seasonality_acf(g.white_noise(240, seed=k)).values["seasonal"] for k in range(200))
    assert false_alarms / 200 <= 0.08
    p = seasonality_periodogram(s).values
    assert p["seasonal"] and p["period"] == pytest.approx(12, abs=0.1)
    assert seasonality_periodogram(w).values["seasonal"] is False
    assert seasonal_kruskal(s, 12).values["seasonal"]
    assert not seasonal_kruskal(w, 12).values["seasonal"]


def test_fisher_g_is_calibrated_on_white_noise():
    rejections = sum(seasonality_periodogram(g.white_noise(120, seed=s)).values["seasonal"] for s in range(400))
    assert rejections / 400 <= 0.08


def test_component_strength():
    strong = component_strength(g.seasonal(240, amplitude=5, slope_per_step=0.05, seed=5), 12).values
    assert strong["seasonal_strength"] > 0.8 and strong["trend_strength"] > 0.8
    weak = component_strength(g.white_noise(240, seed=5), 12).values
    assert weak["seasonal_strength"] < 0.4 and weak["trend_strength"] < 0.4


def test_permutation_entropy_known_values():
    monotone = pd.Series(np.arange(200.0))
    assert permutation_entropy(monotone).values["permutation_entropy"] == pytest.approx(0.0, abs=1e-12)
    assert permutation_entropy(g.white_noise(5000, seed=6)).values["permutation_entropy"] > 0.99


def test_residual_diagnostics():
    good = residual_diagnostics(g.white_noise(300, seed=7)).values
    assert good["residuals_uncorrelated"] and good["residuals_normal"] and good["variance_stable"]
    assert not residual_diagnostics(g.ar1(300, phi=0.7, seed=7)).values["residuals_uncorrelated"]
    growing = g.white_noise(300, seed=7) * np.linspace(0.2, 3, 300)
    assert not residual_diagnostics(growing).values["variance_stable"]
