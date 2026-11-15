"""SPI probabilities checked independently against the fitted gamma CDF and normal inverse."""

import generators as g
import json
import numpy as np
import pandas as pd
import pytest
from scipy import stats

from timedetective.packs.earth.skills.transforms.spi import weather_precip_spi


def test_spi_gamma_transform_and_drought_catalogue():
    rng = np.random.default_rng(83)
    x = pd.Series(rng.gamma(4,20,45*12),index=pd.date_range("1980-01-01",periods=45*12,freq="MS"))
    x.attrs = g.seasonal_weather().attrs
    x.loc["2020-01-01":"2020-12-01"] = .01
    out = weather_precip_spi(x,analyses=["spi"],baseline=[1981,2010],scale=3,seed=44,fit_resamples=99)
    assert out.ok
    json.dumps(out.values, allow_nan=False)
    assert out.values["drought_events"]
    fit = out.values["fits"]["6"]
    value = next(row["spi"] for row in out.values["series"] if row["date"] == "2020-06-01")
    expected = stats.norm.ppf(np.clip(fit["zero_probability"]+(1-fit["zero_probability"])*
        stats.gamma.cdf(.03,fit["shape"],scale=fit["scale"]),1e-8,1-1e-8))
    assert value == pytest.approx(expected)
    assert all(row["spi"] is None for row in out.values["series"][:2])


def test_short_baseline_and_missing_accumulation_are_not_filled():
    x = g.seasonal_weather()
    assert not weather_precip_spi(x,analyses=["spi"],baseline=[2000,2019],scale=3,seed=0,fit_resamples=99).ok
    long = pd.Series(np.tile(np.arange(1,49),12),index=pd.date_range("1977-01-01",periods=48*12,freq="MS"),dtype=float)
    long.attrs = x.attrs
    long.loc["1988-01-01"] = np.nan
    out = weather_precip_spi(long,analyses=["spi"],baseline=[1980,2009],scale=1,seed=0,fit_resamples=99)
    assert out.values["subprocedure_refusals"]
    assert next(row["spi"] for row in out.values["series"] if row["date"] == "1988-01-01") is None
