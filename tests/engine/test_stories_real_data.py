"""The two checks on the cached NASA records. These pin what the real data say today.

They are regression tests on real evidence, not known-answer tests: if a number moves,
either the method changed (say so in docs/story_results.md) or the cache was altered.
"""

import json
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from timedetective.packs.earth.adapters.power import load_power
from timedetective.packs.earth.adapters.stories import load_gsfc_mascons, load_modis_subset, load_power_regional
from timedetective.packs.earth.stories import check_season, check_storage

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data/cache/earth/stories"
SEASON = [4, 5, 6, 7, 8, 9]


def steps(finding):
    return {s.node: json.loads(s.values_json) for s in finding.path}


def storage_inputs(tag):
    return (load_gsfc_mascons(CACHE / f"gsfc_mascons_{tag}.csv"),
            load_power_regional(CACHE / f"power_monthly_PRECTOTCORR_SUM_{tag}_2000_2025_20261115.json", "PRECTOTCORR_SUM"),
            load_power_regional(CACHE / f"power_monthly_GWETPROF_{tag}_2000_2025_20261115.json", "GWETPROF"))


def vegetation(km=5):
    return load_modis_subset(CACHE / f"modis_MOD13Q1_3.0061N_34.1125E_{km}km_20261115.json.gz")


def rain(parameter="IMERG_PRECTOT"):
    return load_power(CACHE / "power_3.006N_34.112E_2000_2025_20261115.json", parameter)


def test_every_cached_file_matches_its_recorded_checksum(tmp_path):
    storage, rainfall, wetness = storage_inputs("nw_india")
    assert storage.attrs["resolution_units"] == 26 and storage.attrs["storage_kind"] == "total_water_storage"
    assert rainfall.attrs["units"] == "mm/month" and wetness.attrs["variable"] == "soil_wetness"
    assert len(vegetation()) == 614
    tampered = tmp_path / "gsfc_mascons_nw_india.csv"
    tampered.write_bytes((CACHE / "gsfc_mascons_nw_india.csv").read_bytes() + b"\n")
    (tmp_path / "gsfc_mascons_nw_india.meta.yaml").write_bytes((CACHE / "gsfc_mascons_nw_india.meta.yaml").read_bytes())
    with pytest.raises(ValueError, match="checksum"):
        load_gsfc_mascons(tampered)


def test_north_west_india_water_storage_is_falling_and_rainfall_does_not_account_for_it():
    storage, rainfall, wetness = storage_inputs("nw_india")
    finding = check_storage(storage, question="Is the water stored under this region changing?", rainfall=rainfall, soil_wetness=wetness)
    v = steps(finding)
    assert v["trend"]["slope_cm_per_year"] == pytest.approx(-3.76, abs=0.05)
    assert v["trend"]["trend_detected"] and v["trend"]["sign_stable"] and not v["handover"]["break_at_handover"]
    assert v["rainfall"]["link"] == "falls_at_average_rainfall" and v["rainfall"]["rainfall_trend"]["direction"] == "increasing"
    assert finding.claim.strength == "significant"
    assert finding.claim.statement.startswith("Total water storage in this region fell by about 3.8 cm")
    assert "have not been separated from groundwater" in finding.claim.statement


def test_the_first_years_agree_with_the_published_rate_for_the_region():
    """Rodell et al. (2009) report 4.0 +/- 1.0 cm a year of groundwater loss, August 2002 to October 2008.

    This is not the same quantity (total storage, not groundwater) nor the same outline (a box,
    not three states), so agreement is a plausibility check, not a validation.
    """
    storage = load_gsfc_mascons(CACHE / "gsfc_mascons_nw_india.csv")["2002-08":"2008-10"].dropna()
    t = (storage.index - storage.index[0]).days / 365.25
    assert 3.0 <= -np.polyfit(t, storage.to_numpy(), 1)[0] <= 5.0


def test_high_plains_decline_is_described_but_not_called_significant():
    storage, rainfall, wetness = storage_inputs("high_plains")
    finding = check_storage(storage, question="Is the water stored under this region changing?", rainfall=rainfall, soil_wetness=wetness)
    v = steps(finding)
    assert v["trend"]["slope_cm_per_year"] == pytest.approx(-1.36, abs=0.05) and not v["trend"]["trend_detected"]
    assert v["trend"]["second_method"]["trend_detected"]   # the less cautious method fires; that alone is not enough
    assert v["rainfall"]["responds_to_rainfall"]
    assert finding.claim.strength == "descriptive" and "On a straight-line fit" in finding.claim.statement


@pytest.mark.parametrize("parameter", ["IMERG_PRECTOT", "PRECTOTCORR"])
@pytest.mark.parametrize("km", [5, 2])
def test_kotido_2009_stands_out_in_both_indicators(parameter, km):
    finding = check_season(vegetation(km), question="How does this season compare?", season_months=SEASON, target_year=2009, rainfall=rain(parameter))
    v = steps(finding)
    assert v["standing"]["rank"] <= 2 and v["standing"]["band"] == "well below usual"
    assert v["rainfall"]["rank"] == 1 and v["rainfall"]["agreement"] == "both_low"
    assert finding.claim.strength == "descriptive"


def test_kotido_2026_has_one_indicator_and_says_so():
    finding = check_season(vegetation(), question="How does this season compare?", season_months=SEASON, target_year=2026, rainfall=rain())
    v = steps(finding)
    assert [r.procedure for r in finding.refusals] == ["season_rainfall"]
    assert v["standing"]["band"] == "within the usual range" and v["standing"]["drift_adjusted"]["band"] == "well below usual"
    assert "drifted upward" in finding.claim.statement and "Rainfall" not in finding.claim.statement


def test_the_app_runs_both_checks_on_cached_data():
    app = AppTest.from_file(str(ROOT / "app/main.py")).run(timeout=60)
    app.radio(key="workspace").set_value("Research tools").run(timeout=60)
    next(b for b in app.button if b.label == "Check the season").click().run(timeout=60)
    next(b for b in app.button if b.label == "Check water storage").click().run(timeout=60)
    assert not app.exception
    assert sum(item.value == "What the record shows" for item in app.subheader) == 2


def groundwater_inputs(tag):
    from timedetective.packs.earth.adapters.gldas import groundwater_estimate, load_gldas_storage
    storage, rainfall, _ = storage_inputs(tag)
    modelled = load_gldas_storage(CACHE / f"gldas_noah025_m_{tag}.json.gz", CACHE / f"gsfc_mascons_{tag}.meta.yaml")
    return groundwater_estimate(storage, modelled), modelled, rainfall


def test_gldas_covers_the_record_and_rejects_a_bundle_for_another_region():
    from timedetective.packs.earth.adapters.gldas import load_gldas_storage
    groundwater, modelled, _ = groundwater_inputs("nw_india")
    assert modelled.isna().sum() == 0 and modelled.index[0] == np.datetime64("2002-01-01")
    assert groundwater.attrs["storage_kind"] == "groundwater" and "surface water" in groundwater.attrs["subtraction"]["not_subtracted"]
    with pytest.raises(ValueError, match="different region"):
        load_gldas_storage(CACHE / "gldas_noah025_m_nw_india.json.gz", CACHE / "gsfc_mascons_high_plains.meta.yaml")


def test_north_west_india_groundwater_estimate_is_falling_and_both_methods_agree():
    groundwater, _, rainfall = groundwater_inputs("nw_india")
    finding = check_storage(groundwater, question="Is the groundwater under this region changing?", rainfall=rainfall)
    v = steps(finding)
    assert v["trend"]["slope_cm_per_year"] == pytest.approx(-3.98, abs=0.05)
    assert v["trend"]["trend_detected"] and v["trend"]["second_method"]["trend_detected"]
    assert v["rainfall"]["link"] == "falls_at_average_rainfall"
    assert finding.claim.strength == "significant"
    assert finding.claim.statement.startswith("Groundwater storage") and "surface water" in finding.claim.statement


def test_high_plains_groundwater_estimate_stays_descriptive():
    groundwater, _, rainfall = groundwater_inputs("high_plains")
    finding = check_storage(groundwater, question="Is the groundwater under this region changing?", rainfall=rainfall)
    assert steps(finding)["trend"]["slope_cm_per_year"] == pytest.approx(-1.28, abs=0.05)
    assert finding.claim.strength == "descriptive"


def joint(tag):
    from timedetective.packs.earth.adapters.mod13c2 import load_mod13c2_region
    from timedetective.packs.earth.stories import check_storage_and_greenness
    groundwater, _, rainfall = groundwater_inputs(tag)
    greenness = load_mod13c2_region(CACHE / f"mod13c2_{tag}.json.gz", CACHE / f"gsfc_mascons_{tag}.meta.yaml")
    return greenness, check_storage_and_greenness(
        groundwater, question="Is the water under these farms running out, and would the fields show it?",
        vegetation=greenness, rainfall=rainfall)


def test_north_west_india_grew_greener_while_its_groundwater_fell():
    greenness, finding = joint("nw_india")
    assert [m["mascon_id"] for m in greenness.attrs["excluded_mascons"]] == [7735]  # Himalayan block, snow every winter
    assert greenness.attrs["skipped_months"][0] == "2026-02"
    v = steps(finding)["greenness"]
    assert v["pattern"] == "greener_while_storage_fell" and v["n_years"] == 24
    assert v["greenness_slope_per_decade"] == pytest.approx(0.037, abs=0.003)
    assert finding.claim.strength == "significant"
    assert "nothing would suggest the water under them was falling" in finding.claim.statement
    assert "does not test that cause" in finding.claim.statement and "leaves out 1 of the region's blocks" in finding.claim.statement


def test_high_plains_claims_no_hidden_decline():
    _, finding = joint("high_plains")
    assert steps(finding)["greenness"]["pattern"] == "no_tested_decline"
    assert "nothing would suggest" not in finding.claim.statement and finding.claim.strength == "descriptive"
