import generators as g
import numpy as np
import pandas as pd
import pytest

from timedetective.skills.transforms.anomaly import anomaly
from timedetective.skills.transforms.deseasonalize import deseasonalize_harmonic, deseasonalize_mstl, deseasonalize_stl
from timedetective.skills.transforms.detrend import detrend_linear, difference, prewhiten
from timedetective.skills.transforms.exceedance import exceedance_counts
from timedetective.skills.transforms.gaps import gap_fill
from timedetective.skills.transforms.regularize import regularize
from timedetective.skills.transforms.smooth import hp_filter, loess_trend, moving_average


def _seasonal_share(x: pd.Series) -> float:
    """Share of variance explained by month-of-year means."""
    x = x.dropna()
    return float(x.groupby(x.index.month).transform("mean").var() / x.var())


def test_regularize_daily_to_monthly_and_refuses_upsampling():
    idx = pd.date_range("2020-01-01", "2020-12-31", freq="D")
    daily = pd.Series(np.arange(len(idx), dtype=float), index=idx).drop(idx[40:80])
    out = regularize(daily, "MS")
    assert out.ok and len(out.series) == 12 and out.series.index.freqstr == "MS"
    assert out.series.iloc[0] == pytest.approx(15.0)
    assert not regularize(g.white_noise(24), "D").ok
    assert not regularize(pd.Series([1.0, 2, 3]), "MS").ok


def test_regularize_leaves_empty_periods_missing():
    idx = pd.date_range("2020-01-01", "2020-12-31", freq="D")
    daily = pd.Series(1.0, index=idx).drop(idx[(idx.month == 3)])
    out = regularize(daily, "MS")
    assert out.values["n_missing"] == 1 and np.isnan(out.series.loc["2020-03-01"])


def test_gap_fill_short_gap_and_refuses_long_gap():
    x = g.seasonal(120, seed=1)
    filled = gap_fill(g.with_gaps(x, [30, 31]), max_gap=2, period=12)
    assert filled.ok and filled.values["n_filled"] == 2 and not filled.series.isna().any()
    assert abs(filled.series.iloc[30] - x.iloc[30]) < 3.5
    long = gap_fill(g.with_gaps(x, [30, 31, 32, 33]), max_gap=2)
    assert not long.ok and "longest gap is 4" in long.refusal.failed
    assert not gap_fill(g.with_gaps(x, [0])).ok
    assert gap_fill(x).values["n_filled"] == 0


def test_seasonal_gap_fill_beats_linear_on_seasonal_data():
    x = g.seasonal(240, amplitude=5, sigma=0.2, seed=2)
    holes = [50, 51, 52, 110, 111, 112]
    gappy = g.with_gaps(x, holes)
    err_seasonal = (gap_fill(gappy, 3, period=12).series.iloc[holes] - x.iloc[holes]).abs().mean()
    err_linear = (gap_fill(gappy, 3).series.iloc[holes] - x.iloc[holes]).abs().mean()
    assert err_seasonal < err_linear


def test_anomaly_removes_the_cycle_and_respects_baseline():
    x = g.seasonal(240, amplitude=5, seed=3)
    out = anomaly(x)
    assert _seasonal_share(x) > 0.8 and _seasonal_share(out.series) < 0.01
    based = anomaly(x, baseline=("2000-01-01", "2009-12-01"))
    assert based.values["baseline_end"] == pd.Timestamp("2009-12-01")
    assert based.series.loc["2000":"2009"].mean() == pytest.approx(0.0, abs=1e-9)
    assert not anomaly(x, baseline=("2000-01-01", "2000-06-01")).ok


@pytest.mark.parametrize("skill,kwargs", [
    (deseasonalize_stl, {"period": 12}),
    (deseasonalize_mstl, {"periods": [12]}),
    (deseasonalize_harmonic, {"period": 12}),
])
def test_deseasonalize_removes_season_and_keeps_trend(skill, kwargs):
    x = g.seasonal(240, amplitude=5, slope_per_step=0.05, seed=4)
    out = skill(x, **kwargs)
    assert out.ok and _seasonal_share(detrend_linear(out.series).series) < 0.05
    slope = np.polyfit(np.arange(240), out.series.to_numpy(), 1)[0]
    assert slope == pytest.approx(0.05, abs=0.01)


def test_deseasonalize_on_noise_changes_little():
    x = g.white_noise(240, seed=4)
    assert deseasonalize_harmonic(x, 12).values["seasonal_amplitude"] < 1.0


def test_harmonic_tolerates_gaps_but_stl_refuses():
    x = g.with_gaps(g.seasonal(240, amplitude=5, seed=5), [20, 21, 22, 23, 24, 100])
    assert deseasonalize_harmonic(x, 12).ok
    assert not deseasonalize_stl(x, 12).ok


def test_smoothers_recover_a_slow_trend():
    x = g.seasonal(240, amplitude=3, slope_per_step=0.05, seed=6)
    truth = 0.05 * np.arange(240)
    ma = moving_average(x, 12).series
    assert ma.isna().sum() == 12 and (ma - truth).abs().max() < 1.0
    lo = loess_trend(deseasonalize_stl(x, 12).series, frac=0.3).series
    assert (lo - truth).abs().max() < 1.0
    hp = hp_filter(deseasonalize_stl(x, 12).series, lamb=129600)
    assert hp.ok and hp.values["endpoint_bias_warning"] and (hp.series - truth).abs().iloc[20:-20].max() < 1.0
    assert not hp_filter(x, lamb=0).ok


def test_difference_detrend_prewhiten():
    walk = g.random_walk(300, seed=7)
    d = difference(walk)
    assert len(d.series) == 299 and abs(np.corrcoef(d.series[:-1], d.series[1:])[0, 1]) < 0.15
    t = detrend_linear(g.linear_trend(240, slope_per_step=0.05, seed=7))
    assert t.values["removed_slope"] == pytest.approx(0.05 * 12, rel=0.1) and t.values["slope_unit"] == "per year"
    assert abs(np.polyfit(np.arange(240), t.series.to_numpy(), 1)[0]) < 1e-6
    red = g.ar1(400, phi=0.7, seed=7)
    w = prewhiten(red)
    assert w.values["lag1_autocorrelation"] == pytest.approx(0.7, abs=0.1)
    assert abs(np.corrcoef(w.series[:-1], w.series[1:])[0, 1]) < 0.12


def test_exceedance_counts_known_answer_and_incomplete_years():
    idx = pd.date_range("2018-01-01", "2020-12-31", freq="D")
    x = pd.Series(0.0, index=idx)
    x.loc["2018-07-01":"2018-07-10"] = 40.0
    x.loc["2019-07-01":"2019-07-25"] = 40.0
    full = exceedance_counts(x, 35.0)
    assert full.series.tolist() == [10.0, 25.0, 0.0]
    partial = exceedance_counts(x.loc[:"2020-03-31"], 35.0)
    assert np.isnan(partial.series.iloc[2]) and partial.values["n_incomplete"] == 1
    assert exceedance_counts(x, 35.0, above=False).series.iloc[0] == 355.0
