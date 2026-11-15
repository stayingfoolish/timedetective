from pathlib import Path

from streamlit.testing.v1 import AppTest

from timedetective.agent.precipitation import distill
from timedetective.packs.earth.adapters.power import load_power
from timedetective.packs.earth.precipitation import run_request

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/cache/earth/power_3N_42E_2000_2024_20261115.json"


def test_cached_weather_form_produces_finding_without_network():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "app/main.py"))
    app.run(timeout=30)
    app.radio(key="workspace").set_value("Research tools").run(timeout=30)
    assert not app.exception
    next(b for b in app.button if b.label == "Investigate cached data").click().run(timeout=30)
    assert not app.exception
    assert any(item.value == "Finding" for item in app.subheader)


def test_precipitation_preview_does_not_acquire_data(monkeypatch):
    def forbidden(**kwargs):
        raise AssertionError("preview must not download")
    monkeypatch.setattr("timedetective.packs.earth.precipitation.fetch_power", forbidden)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "app/main.py")).run(timeout=30)
    app.radio(key="workspace").set_value("Research tools").run(timeout=30)
    next(b for b in app.button if b.label == "Preview distilled request").click().run(timeout=30)
    assert not app.exception and not app.error
    assert app.json


def test_precipitation_offline_button_shows_refusals_without_network(monkeypatch):
    def unavailable(**kwargs):
        raise OSError("offline fixture cache unavailable")
    monkeypatch.setattr("timedetective.packs.earth.precipitation.fetch_power", unavailable)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "app/main.py")).run(timeout=30)
    app.radio(key="workspace").set_value("Research tools").run(timeout=30)
    next(b for b in app.button if b.label == "Fetch and investigate precipitation").click().run(timeout=30)
    assert not app.exception
    assert any("offline fixture" in w.value for w in app.warning)


def test_precipitation_story_walks_through_real_recorded_evidence(monkeypatch, tmp_path):
    plan = distill("Is annual rainfall trending, and do MERRA-2 and IMERG agree?", latitude=3, longitude=42,
        start="2000-01-01", end="2024-12-31", baseline=[2000, 2019], event=[2020, 2022],
        seasons={"annual": list(range(1, 13))}, analyses=["summary", "trend", "agreement"],
        target="seasonal_total", resamples=199)
    bundle = run_request(plan, cache_dir=tmp_path,
        records={p: load_power(RAW, p) for p in plan.products})
    monkeypatch.setattr("timedetective.packs.earth.precipitation.investigate_question", lambda *args, **kwargs: bundle)
    app = AppTest.from_file(str(ROOT / "app/main.py")).run(timeout=90)
    app.radio(key="workspace").set_value("Research tools").run(timeout=90)
    next(b for b in app.button if b.label == "Fetch and investigate precipitation").click().run(timeout=90)
    assert not app.exception
    assert any("What will be checked" == s.value for s in app.subheader)
    app.radio(key="precip_story_stage").set_value("2 · Data").run(timeout=90)
    assert not app.exception
    assert any("Where the records came from" == s.value for s in app.subheader)
    app.radio(key="precip_story_stage").set_value("3 · Checks").run(timeout=90)
    assert not app.exception
    assert any("What the checks recorded" == s.value for s in app.subheader)
    app.radio(key="precip_story_stage").set_value("4 · Answer").run(timeout=90)
    assert not app.exception
    assert any("What the evidence supports" == s.value for s in app.subheader)
    assert any("Precipitation findings are descriptive" in m.value for m in app.info)
