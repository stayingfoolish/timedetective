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


def test_the_demo_opens_on_the_groundwater_answer_with_one_tab_per_step():
    app = opened()
    assert label(app) == ["Label: **significant**"]
    assert any(i.value.startswith("Groundwater storage in this region fell") for i in app.info)
    assert [t.label for t in app.tabs] == [*STEP_TABS, "The label", "The playbook"]
    assert {"Record", "Average yearly change", "Change across the real gap"} <= {m.label for m in app.metric}
    # the weather form is still the first button on the page, and nothing was fetched to get here
    assert app.button[0].label == "Investigate cached data"


def test_the_high_plains_get_the_same_steps_and_a_weaker_label():
    app = opened()
    app.selectbox(key="story_area").select_index(1).run(timeout=90)
    assert not app.exception
    assert label(app) == ["Label: **descriptive**"]
    assert any("did not fire" in m.value for m in app.markdown)


def test_asking_why_is_answered_with_what_the_check_does_not_identify():
    app = opened()
    app.text_input(key="story_q").set_value("Why is the groundwater falling here?").run(timeout=90)
    assert not app.exception
    assert label(app) == ["Label: **significant**"]
    assert any("this check does not identify causes" in m.value for m in app.markdown)


def test_an_area_too_small_for_the_satellites_is_refused_at_the_first_step():
    app = opened()
    app.selectbox(key="story_area").select_index(2).run(timeout=90)
    assert not app.exception
    assert label(app) == []
    assert any("resolution cells" in w.value and "larger region" in w.value for w in app.warning)
    assert sum("This step did not run" in i.value for i in app.info) == len(STEP_TABS) - 1
    assert not app.metric
