"""Distillation precedes I/O; cached real data drive all integration tests."""

from datetime import date
import json
from pathlib import Path

import numpy as np
import pytest

from timedetective.agent.precipitation import distill
from timedetective.packs.earth.adapters import power_api
from timedetective.packs.earth.adapters.power import load_power
from timedetective.packs.earth.precipitation import investigate_question, run_request, render_run

RAW = Path(__file__).resolve().parents[2] / "data/cache/earth/power_3N_42E_2000_2024_20261115.json"
CONTROLS = dict(latitude=3, longitude=42, start="2000-01-01", end="2024-12-31",
    baseline=[2000, 2019], event=[2020, 2022], seasons={"MAM": [3, 4, 5], "OND": [10, 11, 12]}, resamples=199)


def test_distillation_is_explicit_and_precedes_network(monkeypatch, tmp_path):
    def forbidden(**kwargs):
        pytest.fail("network called before a valid distillation")
    monkeypatch.setattr("timedetective.packs.earth.precipitation.fetch_power", forbidden)
    for question, controls in [("Why did rainfall change?", CONTROLS), ("Rainfall trend", {}),
                               ("Rainfall onset", CONTROLS), ("Forecast rainfall", CONTROLS)]:
        result = investigate_question(question, cache_dir=tmp_path, **controls)
        assert result["request"] is None
        assert result["findings"]["distillation"]["refusals"]


def test_distills_supported_questions_and_scale():
    plan = distill("Compare SPI-6 drought and rainfall trend in MERRA and IMERG", **CONTROLS)
    assert {"spi", "trend", "agreement", "period_change"} <= set(plan.analyses)
    assert plan.spi_scale == 6
    with pytest.raises(ValueError, match="conflicts"):
        distill("SPI-6", **CONTROLS, spi_scale=3)
    with pytest.raises(ValueError):
        distill("Rainfall trend", **{**CONTROLS, "latitude": np.nan})


def test_real_records_run_end_to_end_with_global_family_and_refusals(tmp_path):
    records = {p: load_power(RAW, p) for p in ["PRECTOTCORR", "IMERG_PRECTOT"]}
    plan = distill("Compare rainfall trend, abrupt changes, extremes, SPI drought and product agreement", **CONTROLS, target="seasonal_total")
    bundle = run_request(plan, cache_dir=tmp_path, records=records)
    assert list(bundle["findings"]) == plan.products
    for finding in bundle["findings"].values():
        assert finding["claim"]["strength"] == "descriptive"
        assert any("30 baseline" in r["failed"] for r in finding["refusals"])
        assert any("10 complete" in r["failed"] for r in finding["refusals"])
        assert finding["subject"][0]["source"].startswith("https://power.larc.nasa.gov/")
        agreement = json.loads(next(s for s in finding["path"] if s["node"] == "daily_agreement")["values_json"])
        assert agreement["paired_days"] == 9132
    global_evidence = json.loads(bundle["global_family"]["path"][0]["values_json"])
    assert global_evidence["family_size"] == 12
    assert global_evidence["failed_members"] == 4
    assert all(t["p_holm_global"] >= t["p_value"] for t in global_evidence["tests"])
    json.dumps(bundle, allow_nan=False)
    report = render_run(bundle)
    assert "experimental_failed_dependence_calibration" in report and "References" in report


def test_missing_product_is_not_silently_dropped(tmp_path):
    bundle = investigate_question("rainfall trend", cache_dir=tmp_path,
        records={"PRECTOTCORR": load_power(RAW, "PRECTOTCORR")}, **CONTROLS)
    assert bundle["findings"]["IMERG_PRECTOT"]["claim"] is None
    evidence = json.loads(bundle["global_family"]["path"][0]["values_json"])
    assert evidence["family_size"] == 4 and evidence["failed_members"] == 2


def test_api_cache_roundtrip_is_network_free_on_second_call(monkeypatch, tmp_path):
    calls = []
    def fake_download(url):
        calls.append(url)
        return RAW.read_bytes()  # A real recorded provider response, not fabricated weather.
    monkeypatch.setattr(power_api, "download", fake_download)
    kwargs = dict(latitude=3, longitude=42, start=date(2000, 1, 1), end=date(2024, 12, 31),
                  parameter="PRECTOTCORR", cache_dir=tmp_path)
    first = power_api.fetch_power(**kwargs)
    second = power_api.fetch_power(**kwargs, offline=True)
    assert first.equals(second) and len(calls) == 1
    path = next(tmp_path.glob("*/*/response.json"))
    path.write_bytes(path.read_bytes()+b" ")
    with pytest.raises(ValueError, match="checksum"):
        power_api.fetch_power(**kwargs)
    assert len(calls) == 1


@pytest.mark.parametrize("fault", ["coordinates", "dates", "utc", "parameter"])
def test_api_rejects_wrong_response_before_caching(monkeypatch, tmp_path, fault):
    data = json.loads(RAW.read_text())
    if fault == "coordinates": data["geometry"]["coordinates"][0] = 0
    if fault == "dates": data["header"]["start"] = "20010101"
    if fault == "utc": data["header"]["time_standard"] = "LST"
    if fault == "parameter": del data["properties"]["parameter"]["PRECTOTCORR"]
    monkeypatch.setattr(power_api, "download", lambda url: json.dumps(data).encode())
    with pytest.raises(ValueError):
        power_api.fetch_power(latitude=3, longitude=42, start=date(2000,1,1), end=date(2024,12,31),
                              parameter="PRECTOTCORR", cache_dir=tmp_path)
    assert not list(tmp_path.iterdir())


def test_offline_and_provider_failure_are_recorded(monkeypatch, tmp_path):
    result = investigate_question("rainfall trend", **CONTROLS, cache_dir=tmp_path, offline=True)
    assert all(f["claim"] is None and f["refusals"] for f in result["findings"].values())
    def unavailable(**kwargs):
        raise OSError("NASA unavailable")
    monkeypatch.setattr("timedetective.packs.earth.precipitation.fetch_power", unavailable)
    result = investigate_question("rainfall trend", **CONTROLS, cache_dir=tmp_path)
    assert "NASA unavailable" in str(result["findings"])


def test_coordinates_are_checked_for_supplied_records(tmp_path):
    x = load_power(RAW, "PRECTOTCORR")
    result = investigate_question("rainfall trend", **{**CONTROLS, "latitude": 4},
                                  cache_dir=tmp_path, records={"PRECTOTCORR": x})
    assert "spatial support" in str(result["findings"]["PRECTOTCORR"]["refusals"])


def test_conflicting_season_year_and_ambiguous_target_are_refused():
    for question in ["JJA rainfall trend", "Rainfall in 2010–2012", "Trend in rainfall extremes"]:
        with pytest.raises(ValueError):
            distill(question, **CONTROLS)
    plan = distill("Trend in daily maximum rainfall", **{**CONTROLS,"seasons":{"annual":list(range(1,13))}})
    assert plan.target == "rx1day"


def test_only_descriptive_analysis_has_no_global_statistical_claim(tmp_path):
    bundle = investigate_question("Rainfall totals", **CONTROLS, analyses=["summary"],
        products=["PRECTOTCORR"],cache_dir=tmp_path,records={"PRECTOTCORR":load_power(RAW,"PRECTOTCORR")})
    assert bundle["global_family"]["claim"] is None
    assert bundle["global_family"]["refusals"]
    assert "No scientific claim" in render_run(bundle)
