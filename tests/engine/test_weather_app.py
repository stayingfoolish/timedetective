from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_cached_weather_form_produces_finding_without_network():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "app/main.py"))
    app.run(timeout=30)
    assert not app.exception
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert any(item.value == "Finding" for item in app.subheader)


def test_precipitation_preview_does_not_acquire_data(monkeypatch):
    def forbidden(**kwargs):
        raise AssertionError("preview must not download")
    monkeypatch.setattr("timedetective.packs.earth.precipitation.fetch_power", forbidden)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "app/main.py")).run(timeout=30)
    next(b for b in app.button if b.label == "Preview distilled request").click().run(timeout=30)
    assert not app.exception and not app.error
    assert app.json


def test_precipitation_offline_button_shows_refusals_without_network(monkeypatch):
    def unavailable(**kwargs):
        raise OSError("offline fixture cache unavailable")
    monkeypatch.setattr("timedetective.packs.earth.precipitation.fetch_power", unavailable)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "app/main.py")).run(timeout=30)
    next(b for b in app.button if b.label == "Fetch and investigate precipitation").click().run(timeout=30)
    assert not app.exception
    assert any("offline fixture" in w.value for w in app.warning)
