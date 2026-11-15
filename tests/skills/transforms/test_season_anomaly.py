import generators as g
import numpy as np
import pandas as pd
import pytest

from timedetective.skills.transforms.season_anomaly import condition_index, standardized_anomaly
from timedetective.skills.transforms.smooth import savgol_smooth


def _with_bad_last_season(drop: float = 4.0, years: int = 20, seed: int = 1) -> pd.Series:
    """Seasonal series whose final April-September sits `drop` below normal."""
    x = g.seasonal(12 * years, amplitude=5, sigma=1.0, seed=seed)
    last = x.index.year == x.index.year.max()
    x[last & (x.index.month >= 4) & (x.index.month <= 9)] -= drop
    return x


def test_standardized_anomaly_present_and_absent():
    bad = standardized_anomaly(_with_bad_last_season().loc[:"2019-09"])
    assert bad.ok and bad.values["latest_z"] < -2 and bad.values["n_cycles"] == 19
    normal = standardized_anomaly(g.seasonal(240, amplitude=5, seed=1).loc[:"2019-09"])
    assert abs(normal.values["latest_z"]) < 2


def test_standardized_anomaly_is_a_true_z_score_per_month():
    z = standardized_anomaly(g.seasonal(240, amplitude=5, seed=2)).series
    june = z[z.index.month == 6]
    assert june.mean() == pytest.approx(0, abs=1e-9) and june.std(ddof=1) == pytest.approx(1)
    # The seasonal cycle itself is gone: month means are all zero.
    assert z.groupby(z.index.month).mean().abs().max() < 1e-9


def test_standardized_anomaly_tolerates_gaps_and_refuses_short_records():
    x = g.with_gaps(g.seasonal(240, amplitude=5, seed=3), [30, 31, 100])
    out = standardized_anomaly(x)
    assert out.ok and out.series.isna().sum() == 3
    short = standardized_anomaly(g.seasonal(36, amplitude=5, seed=3))
    assert not short.ok and "longer record" in short.refusal.would_change


def test_condition_index_bounds_and_known_extremes():
    x = _with_bad_last_season(drop=8.0)
    out = condition_index(x.loc[:"2019-09"])
    assert out.series.min() == 0 and out.series.max() == 100
    assert out.values["latest_index"] == 0  # the worst September on record scores zero
    normal = condition_index(g.seasonal(240, amplitude=5, seed=1).loc[:"2019-09"])
    assert 0 < normal.values["latest_index"] < 100


def test_savgol_reduces_noise_and_keeps_the_peak():
    t = np.arange(240)
    clean = 5 * np.sin(2 * np.pi * t / 24)
    noisy = pd.Series(clean, index=g.white_noise(240).index) + g.white_noise(240, 0.8, seed=4)
    out = savgol_smooth(noisy, window=9, polyorder=2)
    assert np.abs(out.series - clean).mean() < 0.6 * np.abs(noisy - clean).mean()
    assert out.series.max() > 4.2  # a moving average of the same width would flatten this further
    assert not savgol_smooth(noisy, window=8).ok
