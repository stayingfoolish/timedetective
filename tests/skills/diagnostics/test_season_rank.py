import generators as g
import pandas as pd

from timedetective.skills.diagnostics.season_rank import seasonal_rank


def _series(drop: float, seed: int = 1) -> pd.Series:
    x = g.seasonal(240, amplitude=5, sigma=1.0, seed=seed)
    last = x.index.year == 2019
    x[last & (x.index.month >= 4) & (x.index.month <= 9)] -= drop
    return x


def test_bad_season_is_lowest_on_record():
    out = seasonal_rank(_series(4.0).loc[:"2019-07"], period=12, season_start=3, season_length=6)
    v = out.values
    assert out.ok and v["rank"] == 1 and v["lowest_on_record"] and v["n_seasons"] == 20
    assert v["steps_into_season"] == 4 and v["season_start_time"] == pd.Timestamp("2019-04-01")
    assert v["z_against_past"] < -2 and v["percentile"] == 2.5


def test_ordinary_season_is_not_extreme():
    v = seasonal_rank(_series(0.0).loc[:"2019-07"], period=12, season_start=3, season_length=6).values
    assert not v["lowest_on_record"] and not v["highest_on_record"] and abs(v["z_against_past"]) < 2


def test_rank_matches_a_direct_calculation():
    x = _series(1.0, seed=5).loc[:"2019-06"]
    direct = x[(x.index.month >= 4) & (x.index.month <= 6)].groupby(lambda d: d.year).mean()
    v = seasonal_rank(x, period=12, season_start=3, season_length=6).values
    assert v["rank"] == int((direct < direct.loc[2019]).sum()) + 1
    assert abs(v["season_to_date_mean"] - direct.loc[2019]) < 1e-12


def test_refusals_out_of_season_and_short_record():
    out = seasonal_rank(_series(4.0).loc[:"2019-11"], period=12, season_start=3, season_length=6)
    assert not out.ok and "outside the growing season" in out.refusal.failed
    short = seasonal_rank(g.seasonal(60, amplitude=5).loc[:"2004-06"], period=12, season_start=3, season_length=6)
    assert not short.ok
    assert not seasonal_rank(_series(0.0), period=12, season_start=12).ok
