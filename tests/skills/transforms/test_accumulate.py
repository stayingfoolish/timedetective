import generators as g
import numpy as np
import pandas as pd
import pytest

from timedetective.skills.changepoint.chow import chow_test
from timedetective.skills.transforms.accumulate import cumulative_departure, rolling_accumulation
from timedetective.skills.transforms.deseasonalize import deseasonalize_harmonic
from timedetective.skills.transforms.regularize import regularize
from timedetective.skills.trend.mann_kendall import mann_kendall
from timedetective.skills.trend.sens_slope import sens_slope


def test_rolling_accumulation_known_answer():
    x = pd.Series(np.arange(1.0, 25.0), index=g.white_noise(24).index)
    out = rolling_accumulation(x, 12)
    assert out.series.iloc[:11].isna().all() and out.series.iloc[11] == 78.0 and out.series.iloc[-1] == 222.0
    assert not rolling_accumulation(x, 1).ok


def test_accumulated_rain_tracks_a_slow_store_better_than_monthly_rain():
    rain = g.white_noise(360, 1.0, seed=1) + 3
    store = (rain - rain.mean()).cumsum() * 0.2 + g.white_noise(360, 0.1, seed=2)  # storage integrates rainfall
    acc = rolling_accumulation(rain, 24).series.dropna()
    monthly_r = np.corrcoef(rain.loc[acc.index].diff().dropna(), store.loc[acc.index].diff().dropna())[0, 1]
    change = store.diff(24).dropna()   # storage change over the same 24 months
    acc_r = np.corrcoef(acc.loc[change.index], change)[0, 1]
    assert acc_r > 0.85 > monthly_r


def test_cumulative_departure_finds_the_turn_from_wet_to_dry():
    x = g.white_noise(240, 0.5, seed=3)
    x.iloc[:120] += 1.0   # wet first half, dry second half
    out = cumulative_departure(x)
    assert abs(x.index.get_loc(out.values["highest_time"]) - 119) <= 6
    assert out.series.iloc[-1] == pytest.approx(0, abs=1e-9)
    based = cumulative_departure(x, baseline=("2000-01-01", "2009-12-01"))
    assert based.series.iloc[-1] < -50   # judged against the wet decade, the record ends far below
    flat = cumulative_departure(g.white_noise(240, 0.5, seed=3))
    assert np.ptp(flat.series.to_numpy()) < np.ptp(out.series.to_numpy()) / 3


def test_regularize_min_count_drops_thin_years():
    idx = pd.date_range("2015-01-01", "2020-12-01", freq="MS")
    x = pd.Series(1.0, index=idx).drop(idx[(idx.year == 2017) & (idx.month > 3)])
    out = regularize(x, "YS", min_count=6)
    assert np.isnan(out.series.loc["2017-01-01"]) and out.values["n_missing"] == 1
    assert regularize(x, "YS").values["n_missing"] == 0


def _storage_with_mission_gap(slope_per_month: float, seed: int = 4) -> pd.Series:
    """Monthly storage 2002-2025 with a seasonal cycle and an 11-month gap from mid-2017."""
    idx = pd.date_range("2002-04-01", "2025-12-01", freq="MS")
    t = np.arange(len(idx))
    rng = np.random.default_rng(seed)
    x = pd.Series(slope_per_month * t + 4 * np.sin(2 * np.pi * t / 12) + rng.normal(0, 1.0, len(idx)), index=idx)
    x[(idx >= "2017-07-01") & (idx <= "2018-05-01")] = np.nan
    return x


def test_gap_tolerant_path_recovers_a_trend_across_the_mission_gap():
    """Harmonic deseasonalizing (tolerates gaps), then annual means, then the trend tests."""
    x = _storage_with_mission_gap(-0.05)
    annual = regularize(deseasonalize_harmonic(x, 12).series, "YS", min_count=6).series
    assert annual.isna().sum() == 0 and len(annual) == 24   # 2017 and 2018 each keep six or more months
    assert sens_slope(annual).values["slope"] == pytest.approx(-0.05 * 12, rel=0.15)
    assert mann_kendall(annual).values["direction"] == "decreasing"
    # No artificial step at the mission change.
    assert not chow_test(annual, pd.Timestamp("2018-01-01")).values["break_detected"]


def test_gap_tolerant_path_absent_and_offset_detected():
    flat = _storage_with_mission_gap(0.0)
    annual = regularize(deseasonalize_harmonic(flat, 12).series, "YS", min_count=6).series
    assert not mann_kendall(annual).values["trend_detected"]
    shifted = flat.copy()
    shifted[shifted.index >= "2018-06-01"] += 3.0   # an offset between the two missions
    annual = regularize(deseasonalize_harmonic(shifted, 12).series, "YS", min_count=6).series
    assert chow_test(annual, pd.Timestamp("2018-01-01")).values["break_detected"]
