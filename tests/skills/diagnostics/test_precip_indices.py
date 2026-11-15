"""Known precipitation spell/timing behavior and insufficient-tail-record refusal."""

import generators as g
import json
import numpy as np
import pandas as pd
import pytest
from scipy import stats

from timedetective.packs.earth.skills.diagnostics.precipitation import weather_precip_spells, weather_precip_timing
from timedetective.packs.earth.skills.diagnostics.return_levels import weather_precip_return_levels


def daily(start="2000-01-01", end="2024-12-31"):
    x = pd.Series(0., index=pd.date_range(start,end))
    x.attrs = {**g.seasonal_weather().attrs,"cadence":"daily","units":"mm/day"}
    return x


def test_cross_year_spell_is_not_split_and_missing_days_are_censored():
    x = daily()
    x[:] = 2
    x.loc["2001-12-29":"2002-01-03"] = 0
    x.loc["2002-01-04"] = np.nan
    out = weather_precip_spells(x, analyses=["extremes"],wet_threshold=1).values
    spell = next(s for s in out["spells"] if s["kind"] == "dry")
    assert spell["days"] == 6 and spell["right_censored"] and not spell["left_censored"]
    assert 2002 in out["excluded_years"]


def test_timing_known_wet_season_and_dry_record():
    x = daily()
    x.loc[x.index.month.isin([4,5,6])] = 10
    out = weather_precip_timing(x, analyses=["timing"],baseline=[2000,2019],windows={"wet":["02-01","09-30"]})
    assert len(out.values["timing"]) == 25
    json.dumps(out.values, allow_nan=False)
    assert out.values["timing"][0]["onset"] == "2000-04-01"
    assert out.values["timing"][0]["cessation"] == "2000-06-30"
    x[:] = 0
    assert not weather_precip_timing(x,analyses=["timing"],baseline=[2000,2019],windows={"wet":["02-01","09-30"]}).ok


def test_return_level_refuses_short_record_instead_of_extrapolating():
    out = weather_precip_return_levels(daily(),analyses=["return_levels"],return_periods=[100],seed=0,fit_resamples=99)
    assert not out.ok and "30 consecutive" in out.refusal.failed


def test_gev_conditional_return_level_matches_scipy():
    x = daily("1981-01-01","2024-12-31")
    rng = np.random.default_rng(133)
    maxima = stats.genextreme.rvs(-.05,loc=60,scale=8,size=44,random_state=rng)
    x.loc[x.index.is_year_start] = maxima
    out = weather_precip_return_levels(x,analyses=["return_levels"],return_periods=[2,10],seed=19,fit_resamples=99)
    assert out.ok, out.refusal
    json.dumps(out.values, allow_nan=False)
    params = stats.genextreme.fit(maxima)
    assert out.values["return_levels"][1]["daily_mm"] == pytest.approx(stats.genextreme.isf(.1,*params))
    assert "conditional" in out.values["inference_status"]
