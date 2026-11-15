"""Season check end to end on synthetic records with known answers."""

import json

import generators as g
import numpy as np
import pytest

from timedetective.packs.earth.stories import check_season

SEASON = [4, 5, 6, 7, 8, 9]
EFFECTS = g.year_effects(seed=11)


def step(finding, node):
    return next(json.loads(s.values_json) for s in finding.path if s.node == node)


def run(veg, year, rain=None, question="How does this season compare with earlier ones here?", **kw):
    return check_season(veg, question=question, season_months=SEASON, target_year=year, rainfall=rain, **kw)


def test_a_poor_season_is_ranked_lowest_and_rainfall_agrees():
    veg, rain = g.ndvi_composites(low_year=2017, effects=EFFECTS, seed=1), g.daily_rain(low_year=2017, effects=EFFECTS, seed=2)
    finding = run(veg, 2017, rain)
    standing, rainfall = step(finding, "standing"), step(finding, "rainfall")
    assert standing["rank"] == 1 and standing["lowest_on_record"] and standing["band"] == "well below usual"
    assert rainfall["agreement"] == "both_low" and rainfall["rainfall_and_greenness_move_together"]
    assert finding.claim.strength == "descriptive"
    assert "lowest of 24 seasons" in finding.claim.statement and "Rainfall agrees" in finding.claim.statement
    assert "not crops alone" in finding.claim.statement
    assert not finding.refusals and len(finding.subject) == 2


def test_an_ordinary_season_is_reported_as_ordinary():
    veg, rain = g.ndvi_composites(low_year=2017, effects=EFFECTS, seed=1), g.daily_rain(low_year=2017, effects=EFFECTS, seed=2)
    ordinary = int(np.argsort(np.abs(EFFECTS[:24]))[0]) + 2001
    finding = run(veg, ordinary, rain)
    assert step(finding, "standing")["band"] == "within the usual range"
    assert "within the usual range" in finding.claim.statement


def test_without_rainfall_the_finding_stands_on_one_indicator_and_says_so():
    finding = run(g.ndvi_composites(low_year=2017, seed=1), 2017)
    assert finding.claim is not None and finding.claim.strength == "descriptive"
    assert [r.procedure for r in finding.refusals] == ["season_rainfall"]
    assert any("second indicator" in s for s in finding.would_strengthen)
    assert "Rainfall" not in finding.claim.statement


def test_a_season_in_progress_is_compared_over_the_months_so_far():
    veg = g.ndvi_composites(low_year=2024, seed=3)
    finding = run(veg[veg.index < "2024-07-01"], 2024)
    standing = step(finding, "standing")
    assert standing["months_used"] == [4, 5, 6] and not standing["season_complete"]
    assert "first 3 of 6 season months" in finding.claim.statement
    assert standing["rank"] <= 2


def test_rainfall_that_disagrees_is_reported_not_hidden():
    veg, rain = g.ndvi_composites(low_year=2017, effects=EFFECTS, seed=1), g.daily_rain(effects=EFFECTS, seed=2)
    wet = int(np.argmax(EFFECTS[:24])) + 2001
    veg_low = g.ndvi_composites(low_year=wet, depth=0.2, effects=EFFECTS, seed=1)
    finding = run(veg_low, wet, rain)
    assert step(finding, "rainfall")["agreement"] == "differ"
    assert "does not show the same thing" in finding.claim.statement
    del veg


def test_a_drifting_record_is_flagged():
    finding = run(g.ndvi_composites(drift_per_year=0.006, seed=4), 2020)
    assert step(finding, "standing")["drift"]["record_drifts"]
    assert "moving reference" in finding.claim.statement


def test_questions_beyond_the_scope_are_named_in_the_finding():
    finding = run(g.ndvi_composites(low_year=2017, seed=1), 2017, question="Will the harvest fail this year, and why?")
    for phrase in ("does not identify causes", "makes no forecast", "not a declaration"):
        assert phrase in finding.claim.statement


@pytest.mark.parametrize("kwargs, procedure", [
    ({"target_year": 1990}, "season_audit"),
    ({"season_months": [4, 6, 7]}, "season_audit"),
])
def test_bad_requests_are_refused(kwargs, procedure):
    args = {"question": "q", "season_months": SEASON, "target_year": 2017, **kwargs}
    finding = check_season(g.ndvi_composites(seed=1), **args)
    assert finding.claim is None and finding.refusals[0].procedure == procedure


def test_missing_provenance_is_refused():
    veg = g.ndvi_composites(seed=1)
    veg.attrs = {}
    finding = run(veg, 2017)
    assert finding.claim is None and "missing metadata" in finding.refusals[0].failed


def test_a_short_record_is_refused():
    finding = run(g.ndvi_composites(n_years=6, seed=1), 2004)
    assert finding.claim is None and finding.refusals[0].procedure == "season_standing"


def test_a_cloudy_month_inside_the_target_season_is_refused_not_filled():
    veg = g.ndvi_composites(low_year=2017, seed=1)
    veg[(veg.index >= "2017-06-01") & (veg.index < "2017-07-01")] = np.nan
    finding = run(veg, 2017)
    assert finding.claim is None and "does not fill gaps" in finding.refusals[0].would_change
