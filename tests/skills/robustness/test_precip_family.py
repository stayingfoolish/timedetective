"""Whole-procedure failures must not silently shrink the declared hypothesis family."""

import pandas as pd
import pytest

from timedetective.packs.earth.skills.robustness.precipitation import weather_precip_family, weather_precip_global


def test_failed_procedure_members_retained_as_p_one():
    result = weather_precip_family(pd.Series(dtype=float),trend={"tests":[{"id":"trend:MAM","p_value":.01}]},
        period={},changepoint={},alpha=.05,planned_members=6)
    assert result.values["family_size"] == 6
    assert result.values["failed_members"] == 5
    assert result.values["tests"][0]["p_holm"] == pytest.approx(.06)
    global_result = weather_precip_global(pd.Series(dtype=float),families={"a":result.values,"b":{"tests":[],"failed_members":6}},alpha=.05)
    assert global_result.values["family_size"] == 12
    assert global_result.values["tests"][0]["p_holm_global"] == pytest.approx(.12)
