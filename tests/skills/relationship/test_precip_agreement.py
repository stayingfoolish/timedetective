"""Paired-product discrepancy must not become an accuracy or independence claim."""

import generators as g
import numpy as np
import pandas as pd
import pytest

from timedetective.packs.earth.skills.relationship.precipitation import weather_precip_agreement


def test_known_offset_and_missing_pair():
    x = pd.Series(np.arange(366)%5,index=pd.date_range("2000-01-01",periods=366),dtype=float)
    x.attrs = {**g.seasonal_weather().attrs,"cadence":"daily","units":"mm/day"}
    y = x+1
    y.attrs = x.attrs
    out = weather_precip_agreement(x,companion=y,analyses=["agreement"],wet_threshold=1).values
    assert out["primary_minus_companion_mm_per_day"] == -1
    assert out["rmse_between_products_mm_per_day"] == 1
    assert out["pearson_r"] == pytest.approx(1)
    assert not out["independence_established"]
    y.iloc[10] = np.nan
    assert not weather_precip_agreement(x,companion=y,analyses=["agreement"],wet_threshold=1).ok
