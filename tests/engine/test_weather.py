"""End-to-end known-answer, refusal, provenance and graph safety tests."""

import json
from pathlib import Path

import generators as g
import numpy as np
import pandas as pd
import pytest
import yaml

from timedetective.engine.executor import validate_graph
from timedetective.engine.models import Playbook
from timedetective.packs.earth.run import investigate, discover
from timedetective.packs.earth.skills.diagnostics.weather import weather_audit, weather_extremes
from timedetective.packs.earth.skills.transforms.monthly import weather_monthly
from timedetective.packs.earth.skills.trend.seasonal import seasonal_values, model_evidence
from timedetective.packs.earth.adapters.power import load_power, PARAMETERS
from timedetective.agent.report import render

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/cache/earth/power_3N_42E_2000_2024_20261115.json"
SEASONS = {"MAM": [3, 4, 5], "OND": [10, 11, 12]}


def run(x, **kwargs):
    return investigate(x, question="Did a seasonal event occur, and does it establish permanence?",
                       seasons=SEASONS, **kwargs)


def result(finding, node="seasons"):
    return json.loads(next(s for s in finding.path if s.node == node).values_json)


def test_episode_is_measured_but_not_declared_permanent():
    f = run(g.seasonal_weather(episode=True))
    assert f.claim.strength == "descriptive"
    for s in result(f)["seasons"].values():
        assert s["event_below_threshold_count"] == 3
        assert s["event_mean_anomaly"] < -50
        assert s["long_term"]["best_model"] == "specified_episode"
    assert "do not establish" in f.claim.statement
    assert all(step.source and step.edge_source for step in f.path)
    assert "2020" in next(s for s in f.path if s.node == "seasons").parameters_json


def test_absent_episode_and_true_trend_are_not_forced_to_drought():
    f = run(g.seasonal_weather(slope=2))
    assert all(s["event_mean_anomaly"] > 0 for s in result(f)["seasons"].values())
    assert all(s["long_term"]["sen_slope_per_year"] > 4 for s in result(f)["seasons"].values())


@pytest.mark.parametrize("fault", ["metadata", "duplicate", "gap_date", "negative", "infinity", "units"])
def test_bad_inputs_refuse_without_claim(fault):
    x = g.seasonal_weather()
    if fault == "metadata": x.attrs = {}
    if fault == "duplicate": x.index = pd.DatetimeIndex([x.index[0], *x.index[:-1]])
    if fault == "gap_date": x = x.drop(x.index[4])
    if fault == "negative": x.iloc[2] = -999
    if fault == "infinity": x.iloc[2] = np.inf
    if fault == "units": x.attrs["units"] = "inches/hour"
    f = run(x)
    assert f.claim is None and f.refusals


def test_missing_event_month_is_not_zero_rain_or_silently_dropped():
    x = g.seasonal_weather(episode=True)
    x.loc["2021-04-01"] = np.nan
    f = run(x)
    assert f.claim is None
    assert "incomplete" in f.refusals[-1].failed


def test_monthly_rate_uses_leap_year_days():
    x = g.seasonal_weather().iloc[:3].copy()
    x[:] = 1
    x.attrs["units"] = "mm/day"
    assert weather_monthly(x).series.tolist() == [31, 29, 31]


def test_zero_rain_has_no_infinite_percent_or_spurious_model():
    x = g.seasonal_weather()
    x[:] = 0
    f = run(x)
    assert f.claim is not None
    values = result(f)["seasons"]["MAM"]
    assert values["years"][0]["percent_anomaly"] is None
    assert values["long_term"]["best_model"] == "flat"
    json.dumps(f.model_dump(mode="json"), allow_nan=False)


def test_cross_year_season_and_temperature_weighting():
    x = g.seasonal_weather()
    x[:] = 1
    assert seasonal_values(x, [12, 1, 2]).loc[2001] == 3
    assert pd.isna(seasonal_values(x, [12, 1, 2]).loc[2000])
    x.attrs.update(variable="temperature", units="C")
    x.loc["2001-01-01"] = 10
    assert seasonal_values(x, [1, 2]).loc[2001] == pytest.approx((31*10+28)/59)


def test_bic_matches_library_and_step_is_candidate():
    import statsmodels.api as sm
    years = np.arange(2000, 2025)
    y = np.r_[np.zeros(12), np.ones(13)*5] + np.sin(years)*.1
    out = model_evidence(pd.Series(y, index=years), 2020, 2022)
    assert out["best_model"] == "step"
    flat = sm.OLS(y, np.ones((25, 1))).fit()
    trend = sm.OLS(y, sm.add_constant(years - 2000)).fit()
    assert out["models"]["flat"]["bic"] - out["models"]["trend"]["bic"] == pytest.approx(flat.bic-trend.bic)


def test_daily_missing_and_extremes_known_answer():
    x = pd.Series(0., index=pd.date_range("2000-01-01", "2000-12-31"))
    x.attrs = {**g.seasonal_weather().attrs, "cadence": "daily", "units": "mm/day"}
    x.iloc[5:10] = 2
    row = weather_extremes(x).values["annual_indices"][0]
    assert row["rx1day_mm"] == 2 and row["rx5day_within_year_mm"] == 10
    assert row["wet_days"] == 5 and row["cdd_within_year_days"] == 356
    x.iloc[20] = np.nan
    assert not weather_extremes(x).ok
    assert pd.isna(weather_monthly(x).series.iloc[0])


@pytest.mark.parametrize("intent", ["attribution", "forecast", "SPI", "return_period"])
def test_unimplemented_questions_refuse(intent):
    assert run(g.seasonal_weather(), intent=intent).claim is None


def test_agreement_cannot_create_independence_or_robust_claim():
    x = g.seasonal_weather(episode=True)
    f = run(x, companion=x.copy())
    comparison = result(f, "comparison")
    assert comparison["shared_lineage_declared"]
    assert not comparison["independence_established"]
    assert f.claim.strength == "descriptive"
    y = x.copy()
    y.attrs["spatial_support"] = {"kind": "other"}
    assert any("spatial" in r.failed for r in run(x, companion=y).refusals)


def test_graph_rejects_cycles_ambiguity_and_missing_sources():
    raw = yaml.safe_load((ROOT / "knowledge/playbooks/weather.yaml").read_text())
    procs = {p.stem: yaml.safe_load(p.read_text()) for p in (ROOT / "knowledge/procedures").glob("*/*.yaml")}
    sources = yaml.safe_load((ROOT / "knowledge/sources.yaml").read_text())
    for fault in ["cycle", "source", "duplicate"]:
        pb = Playbook(**raw)
        if fault == "cycle": pb.edges[0].target = "audit"
        if fault == "source": pb.edges[0].source = "invented"
        if fault == "duplicate": pb.edges.append(pb.edges[0])
        with pytest.raises(ValueError): validate_graph(pb, procs, sources)


def test_discovery_keeps_every_input_and_does_not_assume_location():
    out = discover({"blind_a": g.seasonal_weather(), "blind_b": g.seasonal_weather(episode=True)},
                   seasons=SEASONS, baseline=(2000, 2019), event=(2020, 2022))
    assert out["search_family"] == ["blind_a", "blind_b"]
    assert out["n_locations"] == 2
    assert all(v["claim"]["strength"] == "descriptive" for v in out["findings"].values())


@pytest.mark.parametrize("parameter", PARAMETERS)
def test_real_cached_data_runs_offline(parameter):
    x = load_power(RAW, parameter)
    assert len(x) == 9132
    f = run(x)
    assert f.claim is not None, f.refusals
    assert f.subject[0].source.startswith("https://power.larc.nasa.gov/")
    assert "synthetic" not in f.subject[0].metadata_json
    assert render(f).startswith("# Weather evidence report")
    json.dumps(f.model_dump(mode="json"), allow_nan=False)


def test_adapter_refuses_corrupted_cached_input(tmp_path):
    copy = tmp_path / "copy.json"
    copy.write_bytes(RAW.read_bytes() + b" ")
    with pytest.raises(ValueError, match="checksum"):
        load_power(copy, "PRECTOTCORR", RAW.with_suffix(".meta.yaml"))


def test_invalid_metadata_and_causal_question_are_refusals():
    x = g.seasonal_weather()
    x.attrs["source"] = None
    assert run(x).claim is None
    f = investigate(g.seasonal_weather(), question="Why did rainfall decline?")
    assert f.claim is None and "unsupported" in f.refusals[0].failed
