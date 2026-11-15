"""End-to-end null/strong-signal checks cannot bypass the uncalibrated claim cap."""

import json
from pathlib import Path

import generators as g
import pandas as pd
import pytest

from timedetective.packs.earth.precipitation import investigate_question


@pytest.mark.parametrize("kind",["gamma","intermittent","long_memory"])
def test_full_precipitation_pipeline_keeps_inference_experimental(kind,tmp_path):
    annual = g.annual_precipitation_null(25,.6,123,kind)
    index = pd.date_range("2000-01-01","2024-12-31")
    x = pd.Series([annual[d.year-2000]/(366 if d.is_leap_year else 365) for d in index],index=index,name="synthetic")
    x.attrs = {**g.seasonal_weather().attrs,"cadence":"daily","units":"mm/day",
               "spatial_support":{"kind":"point_query","latitude":3.,"longitude":42.}}
    out = investigate_question("Rainfall trend and abrupt change",latitude=3,longitude=42,start="2000-01-01",end="2024-12-31",
        baseline=[2000,2014],event=[2015,2024],cache_dir=tmp_path,records={"PRECTOTCORR":x},products=["PRECTOTCORR"],resamples=199)
    assert out["findings"]["PRECTOTCORR"]["claim"]["strength"] == "descriptive"
    tests = json.loads(out["global_family"]["path"][0]["values_json"])["tests"]
    assert tests and all(t["inference_status"] == "experimental_failed_dependence_calibration" for t in tests)
