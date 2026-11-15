"""Size and test the change in annual water storage."""

import numpy as np
import pandas as pd
from scipy.stats import t as student_t, theilslopes

from timedetective.packs.earth.skills.common import plain
from timedetective.skills.detectability.detectable_trend import minimum_detectable_trend
from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse
from timedetective.skills.trend.drift import drift_test
from timedetective.skills.trend.linearity import linearity_check
from timedetective.skills.trend.mann_kendall import mann_kendall_prewhitened
from timedetective.skills.trend.sens_slope import sens_slope

MAX_TRIM_YEARS = 4


@register("storage_trend")
def storage_trend(annual: pd.Series, annual_values: dict, audit_values: dict) -> SkillResult:
    """Sen slope with its range, one pre-declared significance test, and what the record could have shown.

    The significance test is the drift test on yearly changes, always: it keeps its
    false-alarm rate whether the record wobbles around a line or wanders like a random walk
    (docs/calibration.md). Choosing a test after looking at the data would undo that.
    Mann-Kendall after prewhitening is run as a second method and reported; on its own it is
    not enough, because it false-alarms on records that wander slowly. Also reports the
    smallest trend the record could detect, whether the change is steady or bending, and
    whether the direction survives dropping up to four years from either end.
    """
    name = "storage_trend"
    slope, test, second = sens_slope(annual), drift_test(annual), mann_kendall_prewhitened(annual)
    floor, shape = minimum_detectable_trend(annual), linearity_check(annual)
    for part in (slope, test, second, floor, shape):
        if not part.ok:
            return refuse(name, part.refusal.failed, part.refusal.would_change)
    years, values = annual.index.year.to_numpy(dtype=float), annual.to_numpy(dtype=float)
    windows = []
    for head in range(MAX_TRIM_YEARS + 1):
        for tail in range(MAX_TRIM_YEARS + 1):
            keep = slice(head, len(values) - tail)
            windows.append({"first_year": int(years[keep][0]), "last_year": int(years[keep][-1]),
                            "slope": float(theilslopes(values[keep], years[keep])[0])})
    signs = {np.sign(w["slope"]) for w in windows}
    rate = slope.values["slope"]
    # Two intervals, and the wider one is reported. The Sen interval assumes independent years and is too
    # narrow when departures persist; the second widens the standard error for lag-1 autocorrelation and
    # uses a t quantile for the reduced number of effectively independent years (docs/calibration.md).
    r1 = min(max(floor.values["lag1_autocorrelation"], 0.0), 0.95)
    effective_n = len(annual) * (1 - r1) / (1 + r1)
    half = float(student_t.ppf(0.975, max(effective_n - 2, 2.0))) * floor.values["slope_standard_error"]
    low, high = min(slope.values["ci_low"], rate - half), max(slope.values["ci_high"], rate + half)
    detected = bool(test.values["trend_detected"])
    detectable = abs(rate) >= floor.values["minimum_detectable_trend"]
    span = years[-1] - years[0]
    kind = audit_values["storage_kind"]
    noun = "Groundwater storage" if kind == "groundwater" else "Total water storage"
    unit = "cm of water per year"
    first, last = int(years[0]), int(years[-1])
    verb = "fell" if rate < 0 else "rose"
    near, far = sorted([abs(low), abs(high)])
    size = f"about {abs(rate):.1f} {unit} between {first} and {last} (range {near:.1f} to {far:.1f})"
    excludes_zero = low > 0 or high < 0
    if detected:
        bend = ""
        if shape.values["curved"]:
            speeding = np.sign(shape.values["quadratic_coefficient"]) == np.sign(rate)
            bend = " The pace was not steady: it " + ("quickened" if speeding else "slowed") + " over the record."
        statement = f"{noun} in this region {verb} by {size}, about {abs(rate) * span:.0f} cm in total.{bend}"
    elif excludes_zero:
        statement = (f"On a straight-line fit, {noun.lower()} in this region {verb} by {size}. Year-to-year changes vary "
                     "too much for that to pass this project's significance test: a record that simply wanders could look like this.")
    else:
        statement = (f"{noun} in this region shows no clear trend between {first} and {last}. "
                     f"The record could have shown a steady change of about {floor.values['minimum_detectable_trend']:.1f} {unit} or more.")
    limits = ["It does not say why the storage changed.",
              "It is a regional average; places inside the region can differ."]
    limits += list(audit_values.get("not_answered", []))
    if kind == "groundwater":
        subtraction = audit_values.get("subtraction") or {}
        limits.insert(0, "This is an estimate: modelled soil moisture and snow were subtracted from total storage"
                         + (f" ({subtraction['model']})" if subtraction.get("model") else "") + "; "
                         + (subtraction.get("not_subtracted") or "surface water was not subtracted") + ".")
    if kind == "total_water_storage":
        limits.insert(0, "This is all stored water together; soil moisture and surface water have not been separated from groundwater.")
    return SkillResult(name, plain({
        "slope_cm_per_year": rate, "slope_interval": [low, high], "total_change_cm": rate * span,
        "interval_method": "wider of the Sen interval and an autocorrelation-adjusted t interval",
        "sen_interval": [slope.values["ci_low"], slope.values["ci_high"]], "effective_years": effective_n,
        "test": "drift_test", "trend_detected": detected, "direction": test.values["direction"],
        "p_value": test.values["p_value"], "alpha": test.values["alpha"], "n_years": len(values),
        "mean_yearly_change_cm": test.values["mean_change"], "lag1_of_yearly_changes": test.values["lag1_of_changes"],
        "second_method": {"test": "mann_kendall_prewhitened", "trend_detected": bool(second.values["trend_detected"]),
                          "p_value": second.values["p_value"],
                          "note": "reported for comparison; not accepted alone because it false-alarms on slow wander"},
        "minimum_detectable_trend": floor.values["minimum_detectable_trend"], "slope_exceeds_detectable": detectable,
        "annual_lag1_autocorrelation": floor.values["lag1_autocorrelation"],
        "curved": shape.values["curved"], "curvature_p_value": shape.values["p_value"],
        "sign_stable": len(signs) == 1, "trimmed_windows": windows,
        "slope_range_over_windows": [min(w["slope"] for w in windows), max(w["slope"] for w in windows)],
        "provider_leakage_trend_uncertainty": (audit_values.get("provider_uncertainty") or {}).get("leakage_trend_cm_per_year"),
        "conclusion": {
            "statement_type": "storage_change", "statement": statement, "limits": limits,
            "evidence": {"test": "drift_test", "detected": detected, "n": len(values),
                         "persistence": test.values["lag1_of_changes"],
                         "second_method_agrees": bool(second.values["trend_detected"])
                         and second.values["direction"] == test.values["direction"],
                         "exceeds_detectable": bool(detectable), "sign_stable": len(signs) == 1,
                         "artifact_flag": None, "independent_record_agrees": None},
            "would_strengthen": ["An independent record for the same region, such as observation wells.",
                                 "Subtracting modelled soil moisture, snow and surface water, to isolate groundwater."
                                 if kind == "total_water_storage" else "The uncertainty of the subtracted model carried into the result."]}}))
