"""The critic alone decides claim strength, from recorded evidence."""

import pytest

from timedetective.engine.critic import CALIBRATED, strength_for

GOOD = {"test": "drift_test", "detected": True, "n": 25, "persistence": 0.2, "exceeds_detectable": True,
        "sign_stable": True, "artifact_flag": False, "second_method_agrees": True, "independent_record_agrees": True}


def test_full_evidence_reaches_robust():
    assert strength_for(GOOD) == ("robust", [])


@pytest.mark.parametrize("change", [{"sign_stable": False}, {"artifact_flag": None}, {"second_method_agrees": False},
                                    {"independent_record_agrees": None}, {"independent_record_agrees": False}])
def test_missing_robustness_evidence_stops_at_significant(change):
    strength, held_back = strength_for({**GOOD, **change})
    assert strength == "significant" and held_back


@pytest.mark.parametrize("change", [{"detected": False}, {"test": "mann_kendall"}, {"test": "mann_kendall_prewhitened"},
                                    {"test": None}, {"n": 12}, {"n": 60},
                                    {"persistence": 0.7}, {"persistence": None}, {"exceeds_detectable": False},
                                    {"artifact_flag": True}])
def test_anything_outside_the_calibrated_conditions_stays_descriptive(change):
    strength, held_back = strength_for({**GOOD, **change})
    assert strength == "descriptive" and held_back


def test_only_the_drift_test_is_trusted_for_significance():
    """Prewhitened Mann-Kendall false-alarms on slow wander (docs/calibration.md), so it cannot promote a claim alone."""
    assert set(CALIBRATED) == {"drift_test"}
