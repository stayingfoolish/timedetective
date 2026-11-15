"""Water storage check end to end on synthetic records with known answers."""

import json

import generators as g
import pytest

from timedetective.packs.earth.stories import check_storage


def step(finding, node):
    return next(json.loads(s.values_json) for s in finding.path if s.node == node)


def run(storage, rain=None, question="Is the water stored under this region changing?", **kw):
    return check_storage(storage, question=question, rainfall=rain, **kw)


def test_a_steady_decline_is_sized_and_tested_across_the_mission_gap():
    finding = run(g.water_storage(slope_per_year=-1.5, seed=1))
    trend = step(finding, "trend")
    assert trend["trend_detected"] and trend["slope_cm_per_year"] == pytest.approx(-1.5, abs=0.15)
    assert trend["slope_interval"][0] <= trend["sen_interval"][0] and trend["slope_interval"][1] >= trend["sen_interval"][1]
    assert trend["sign_stable"] and trend["slope_exceeds_detectable"]
    thin = step(finding, "annual")["thin_years"]
    assert thin["2017"] == 5 and thin["2018"] == 5  # the real record's pattern: kept, and listed
    # Calibrated test fired inside its conditions; no independent record, so not "robust".
    assert finding.claim.strength == "significant"
    assert "fell by about 1." in finding.claim.statement and "cm of water per year" in finding.claim.statement
    assert any("independent record" in s.lower() for s in finding.would_strengthen)


def test_the_reported_range_usually_contains_the_true_rate():
    """Coverage across seeds, including persistent noise where the plain Sen interval is too narrow."""
    for phi, floor in ((0.5, 0.9), (0.9, 0.8)):
        inside = []
        for seed in range(40):
            low, high = step(run(g.water_storage(slope_per_year=-1.5, phi=phi, seed=seed)), "trend")["slope_interval"]
            inside.append(low < -1.5 < high)
        assert sum(inside) / len(inside) >= floor


def test_a_flat_record_reports_what_it_could_have_shown():
    finding = run(g.water_storage(slope_per_year=0.0, seed=2))
    assert not step(finding, "trend")["trend_detected"]
    assert finding.claim.strength == "descriptive"
    assert "no clear trend" in finding.claim.statement and "could have shown" in finding.claim.statement


def test_total_storage_is_never_called_groundwater():
    total = run(g.water_storage(slope_per_year=-1.5, seed=1))
    ground = run(g.water_storage(slope_per_year=-1.5, seed=1, kind="groundwater"))
    assert total.claim.statement.startswith("Total water storage") and "have not been separated" in total.claim.statement
    assert ground.claim.statement.startswith("Groundwater storage") and "have not been separated" not in ground.claim.statement


def test_a_region_smaller_than_the_product_resolves_is_refused():
    finding = run(g.water_storage(slope_per_year=-1.5, cells=6, seed=1))
    assert finding.claim is None
    assert "cannot separate an area this small" in finding.refusals[0].would_change


def test_an_unlabelled_series_is_refused():
    storage = g.water_storage(seed=1)
    del storage.attrs["storage_kind"]
    assert run(storage).claim is None


def test_a_short_record_is_refused():
    finding = run(g.water_storage(slope_per_year=-1.5, seed=1)["2002":"2012"])
    assert finding.claim is None and "15 are needed" in finding.refusals[0].failed


def test_an_offset_between_the_missions_cannot_pass_as_a_significant_trend():
    """A step at the mission change makes the trend test fire; the caution keeps the claim descriptive."""
    for seed in range(5):
        finding = run(g.water_storage(slope_per_year=0.0, offset_at_handover=-8.0, seed=seed))
        assert step(finding, "handover")["break_at_handover"]
        assert "gap between the two satellite missions" in finding.claim.statement
        assert finding.claim.strength == "descriptive"


def test_a_steady_decline_does_not_trigger_the_mission_gap_caution():
    flagged = [step(run(g.water_storage(slope_per_year=-1.5, phi=0.8, seed=seed)), "handover")["break_at_handover"] for seed in range(30)]
    assert sum(flagged) <= 4


def test_a_wandering_record_with_a_fitted_slope_is_not_called_significant():
    """A random walk often has a clear straight-line slope; the wording must say why that is not enough."""
    import numpy as np
    seen = 0
    for seed in range(30):
        x = g.water_storage(phi=0.0, sigma=0.3, seed=seed)
        x = x + np.random.default_rng(500 + seed).normal(0, 0.6, len(x)).cumsum()
        finding = run(x)
        trend = step(finding, "trend")
        if not trend["trend_detected"] and (trend["slope_interval"][0] > 0 or trend["slope_interval"][1] < 0):
            seen += 1
            assert finding.claim.strength == "descriptive"
            assert "On a straight-line fit" in finding.claim.statement and "simply wanders" in finding.claim.statement
    assert seen >= 3


def test_storage_that_only_follows_rainfall_is_described_as_following_rainfall():
    rain = g.monthly_rain(seed=5)
    finding = run(g.water_storage(slope_per_year=0.0, rain=rain, response=2.0, sigma=0.5, seed=6), rain)
    link = step(finding, "rainfall")
    assert link["link"] == "follows_rainfall" and link["responds_to_rainfall"]
    assert link["response_cm_per_100mm"] == pytest.approx(2.0, abs=0.6)
    assert "follow rainfall" in finding.claim.statement


def test_a_decline_beyond_rainfall_is_separated_from_rainfall():
    rain = g.monthly_rain(seed=5)
    finding = run(g.water_storage(slope_per_year=-2.0, rain=rain, response=2.0, sigma=0.5, seed=6), rain)
    link = step(finding, "rainfall")
    assert link["link"] == "falls_at_average_rainfall"
    assert link["storage_change_at_average_rainfall_cm_per_year"] == pytest.approx(-2.0, abs=0.5)
    assert "rainfall" in finding.claim.statement and "does not say why" in finding.claim.statement


def test_without_rainfall_the_trend_finding_still_stands():
    finding = run(g.water_storage(slope_per_year=-1.5, seed=1))
    assert [r.procedure for r in finding.refusals] == ["storage_rainfall"]
    assert finding.claim is not None


def test_cause_and_forecast_questions_are_answered_only_as_far_as_the_record_goes():
    finding = run(g.water_storage(slope_per_year=-1.5, seed=1), question="Why is the groundwater falling and when will it run out?")
    assert "does not identify causes" in finding.claim.statement and "makes no forecast" in finding.claim.statement
