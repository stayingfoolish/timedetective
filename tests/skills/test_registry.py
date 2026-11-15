"""Every procedure YAML has exactly one registered skill, and the reverse."""

from pathlib import Path

import pandas as pd
import pytest

import timedetective.skills  # noqa: F401  (registers everything)
from timedetective.skills import registry
from timedetective.skills.result import SkillResult

ROOT = Path(__file__).resolve().parents[2]


def test_registry_matches_knowledge():
    yaml_names = sorted(p.stem for p in (ROOT / "knowledge" / "procedures").glob("*/*.yaml"))
    assert registry.names() == yaml_names


def test_skill_lives_in_its_category_folder():
    for path in (ROOT / "knowledge" / "procedures").glob("*/*.yaml"):
        module = registry.get(path.stem).__module__
        assert module.startswith(f"timedetective.skills.{path.parent.name}."), path.stem


SINGLE_SERIES = [
    n for n in registry.names()
    if n not in {
        "lagged_cross_correlation", "partial_correlation", "rolling_regression", "decoupling_test",
        "cointegration_engle_granger", "johansen", "slope_difference", "independent_record_check",
        "fdr_correction", "chow_test", "seasonal_kruskal", "component_strength", "deseasonalize_stl",
        "deseasonalize_mstl", "deseasonalize_harmonic", "moving_average", "hp_filter",
        "exceedance_counts", "record_length_needed", "block_bootstrap_slope", "seasonal_kendall",
        "savgol_smooth",
    }
]


@pytest.mark.parametrize("name", SINGLE_SERIES)
def test_too_short_is_a_refusal_not_an_exception(name):
    result = registry.get(name)(pd.Series([1.0]))
    assert isinstance(result, SkillResult)
    if name not in {"record_summary", "gap_audit"}:
        assert not result.ok
        assert result.refusal.failed and result.refusal.would_change


@pytest.mark.parametrize("name", [n for n in SINGLE_SERIES if n not in {"record_summary", "gap_audit", "gap_fill", "regularize", "anomaly", "standardized_anomaly", "condition_index"}])
def test_missing_values_are_a_refusal(name):
    x = pd.Series(range(300), dtype=float)
    x.iloc[50] = float("nan")
    result = registry.get(name)(x)
    assert not result.ok and "missing" in result.refusal.failed
