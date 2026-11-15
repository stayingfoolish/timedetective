"""Water storage beside greenness, end to end on synthetic records with known answers."""

import json

import generators as g

from timedetective.packs.earth.stories import check_storage_and_greenness

QUESTION = "Is the water under this region falling, and would the fields show it?"


def step(finding, node):
    return next((json.loads(s.values_json) for s in finding.path if s.node == node), None)


def run(slope, drift, rain_seed=5, seed=1, vegetation=True):
    rain = g.monthly_rain(seed=rain_seed, start_year=2000)
    storage = g.water_storage(slope_per_year=slope, seed=seed)
    green = g.ndvi_composites(n_years=24, start_year=2002, drift_per_year=drift, seed=seed) if vegetation else None
    return check_storage_and_greenness(storage, question=QUESTION, vegetation=green, rainfall=rain)


def test_fields_greening_while_storage_falls_is_named_and_does_not_change_the_claim_strength():
    finding = run(slope=-2.0, drift=0.004)
    green = step(finding, "greenness")
    assert green["pattern"] == "greener_while_storage_fell" and green["greenness_slope_per_decade"] > 0
    assert green["spearman_storage_greenness"] < 0  # greener as storage falls
    assert "nothing would suggest the water under them was falling" in finding.claim.statement
    assert "does not test that cause" in finding.claim.statement
    assert finding.claim.strength == "significant"  # set by the storage evidence alone


def test_flat_greenness_on_falling_storage_is_greenness_held():
    assert step(run(slope=-2.0, drift=0.0), "greenness")["pattern"] == "green_held_while_storage_fell"


def test_greenness_falling_with_storage_is_both_fell():
    assert step(run(slope=-2.0, drift=-0.01), "greenness")["pattern"] == "both_fell"


def test_a_small_undetected_dip_is_not_called_no_decline():
    finding = run(slope=-2.0, drift=-0.005)
    assert step(finding, "greenness")["pattern"] == "green_held_while_storage_fell"
    assert "no detectable decline" in finding.claim.statement and "not distinguishable from no change" in finding.claim.statement


def test_no_hidden_decline_is_claimed_when_storage_did_not_fall():
    finding = run(slope=0.0, drift=0.004, seed=2)
    assert step(finding, "greenness")["pattern"] == "no_tested_decline"
    assert "nothing would suggest" not in finding.claim.statement


def test_without_vegetation_the_storage_finding_still_stands_and_the_gap_is_a_refusal():
    finding = run(slope=-2.0, drift=0.0, vegetation=False)
    assert finding.claim is not None and finding.claim.strength == "significant"
    assert any(r.procedure == "storage_greenness" and "vegetation" in r.failed for r in finding.refusals)
