"""The walkthrough at the top of the demo: the README's question, run live on the cached NASA records."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[2] / "app/main.py")
STEP_TABS = ["1 Underground?", "2 Falling?", "3 Noise?", "4 Satellites?", "5 Dry spell?", "6 Fields?"]


def opened() -> AppTest:
    app = AppTest.from_file(APP).run(timeout=90)
    assert not app.exception
    return app


def label(app: AppTest) -> list[str]:
    return [m.value for m in app.markdown if m.value.startswith("Label:")]


def follow_to_verdict(app: AppTest, steps: int = 7) -> AppTest:
    for _ in range(steps):
        app.button(key="story_next").click().run(timeout=90)
        assert not app.exception
    return app


def test_the_demo_opens_on_a_compact_groundwater_story_with_an_optional_evidence_trail():
    app = opened()
    assert label(app) == []
    assert any("Follow the water" in m.value for m in app.markdown)
    assert not app.tabs
    assert not any(b.label == "Investigate cached data" for b in app.button)
    assert not any(e.label == "Everything the check recorded, and downloads" for e in app.expander)
    app.toggle(key="story_full_evidence").set_value(True).run(timeout=90)
    assert any(e.label == "Everything the check recorded, and downloads" for e in app.expander)
    assert [t.label for t in app.tabs] == [*STEP_TABS, "The label", "The playbook"]
    assert {"Record", "Average yearly change", "Change across the real gap"} <= {m.label for m in app.metric}
    assert any("One question. Six evidence checks." in m.value for m in app.markdown)
    follow_to_verdict(app)
    assert label(app) == ["Label: **significant**"]
    assert any(i.value.startswith("Groundwater storage in this region fell") for i in app.info)


def test_guide_moves_backward_and_restarts_for_a_new_area():
    app = opened()
    app.button(key="story_next").click().run(timeout=90)
    assert any("How can anyone know" in s.value for s in app.subheader)
    app.button(key="story_previous").click().run(timeout=90)
    assert any(s.value == "The question" for s in app.subheader)
    app.button(key="story_next").click().run(timeout=90)
    app.selectbox(key="story_area").select_index(1).run(timeout=90)
    assert any(s.value == "The question" for s in app.subheader)


def test_handover_clue_explains_the_comparison_and_caution_cutoff():
    app = opened()
    for _ in range(4):
        app.button(key="story_next").click().run(timeout=90)
    assert not app.exception
    assert any("21 <span>of 233</span>" in m.value for m in app.markdown)
    assert any("conservative rank is" in m.value and "9.4%" in m.value for m in app.markdown)
    assert any("No handover caution" in m.value for m in app.markdown)


def test_the_high_plains_get_the_same_steps_and_a_weaker_label():
    app = opened()
    app.selectbox(key="story_area").select_index(1).run(timeout=90)
    assert not app.exception
    follow_to_verdict(app)
    assert label(app) == ["Label: **descriptive**"]
    assert any("wanders" in m.value for m in app.info)


def test_asking_why_is_answered_with_what_the_check_does_not_identify():
    app = opened()
    app.text_input(key="story_q").set_value("Why is the groundwater falling here?").run(timeout=90)
    assert not app.exception
    follow_to_verdict(app)
    assert label(app) == ["Label: **significant**"]
    assert any("this check does not identify causes" in m.value for m in app.info)


def test_an_area_too_small_for_the_satellites_is_refused_at_the_first_step():
    app = opened()
    app.selectbox(key="story_area").select_index(2).run(timeout=90)
    assert not app.exception
    assert label(app) == []
    app.button(key="story_next").click().run(timeout=90)
    assert any("resolution cells" in w.value and "larger region" in w.value for w in app.warning)
    app.toggle(key="story_full_evidence").set_value(True).run(timeout=90)
    assert sum("This step did not run" in i.value for i in app.info) == len(STEP_TABS) - 1
    assert not app.metric
    follow_to_verdict(app, 1)
    assert any("stopped before it could make a claim" in w.value for w in app.warning)
