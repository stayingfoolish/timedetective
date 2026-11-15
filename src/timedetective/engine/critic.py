"""Only this module assigns claim strength.

A procedure may report evidence (which test ran, whether it fired, how persistent the
noise is) and a plain statement of what it measured. It never states how strong the
claim is. The rules below decide that, from the recorded evidence alone.

Ladder:
  descriptive  what the record shows, with a size and a range. The default.
  significant  a test that this project has calibrated fired, inside the conditions it
               was calibrated for, the change is larger than the record's detection floor,
               and no artifact caution has been raised.
  robust       significant, the direction survives changing the period, a second method
               agrees, and an independent record agrees.
"""

import json

from timedetective.engine.models import Claim, Finding

# Tests allowed to support "significant", with the conditions under which the false-alarm
# rate was measured at or below 5% on trend-free series (docs/calibration.md). Outside
# these conditions the claim stays descriptive. Never widen a bound to pass a case.
# "persistence" is the lag-1 correlation of the step-to-step changes the test works on.
CALIBRATED = {
    "drift_test": {"min_n": 20, "max_n": 30, "max_persistence": 0.5},
}

CLOSING = {
    "descriptive": "This describes the record. It has not met this project's bar for calling a change statistically significant.",
    "significant": ("A change this large is unlikely to be chance: the test used gives a false alarm about 1 time in 20 or less "
                    "on trend-free records, including ones that wander from year to year. "
                    "Natural swings much longer than the record cannot be ruled out."),
    "robust": ("The change passes the calibrated test, keeps its direction when the period is changed, "
               "a second method agrees, and an independent record agrees."),
}

WEATHER_STATEMENT = ("The recorded calculations describe the supplied data and spatial support. "
                     "They do not establish a permanent climate change, cause, forecast, or absence of change.")


def _conclusion(finding: Finding) -> dict | None:
    """The most recent conclusion a procedure recorded on the path taken, if any."""
    for step in reversed(finding.path or []):
        values = json.loads(step.values_json)
        if isinstance(values.get("conclusion"), dict):
            return values["conclusion"]
    return None


def strength_for(evidence: dict) -> tuple[str, list[str]]:
    """Claim strength supported by recorded evidence, and what held it back."""
    held_back = []
    rule = CALIBRATED.get(evidence.get("test"))
    if rule is None:
        return "descriptive", ["No calibrated significance test applies to this kind of statement."]
    if not evidence.get("detected"):
        return "descriptive", ["The calibrated significance test did not fire."]
    n, persistence = evidence.get("n"), evidence.get("persistence")
    if n is None or not rule["min_n"] <= n <= rule["max_n"]:
        held_back.append(f"The record length ({n}) is outside the range the test was calibrated for "
                         f"({rule['min_n']} to {rule['max_n']}).")
    if persistence is None or persistence > rule["max_persistence"]:
        held_back.append("Successive changes are more alike than the test was calibrated for, or that could not be measured.")
    if not evidence.get("exceeds_detectable"):
        held_back.append("The change is smaller than the smallest steady trend this record can reliably detect.")
    if evidence.get("artifact_flag") is True:
        held_back.append("An artifact caution was raised, so part of the change may come from the instruments rather than the water.")
    if held_back:
        return "descriptive", held_back
    if not evidence.get("sign_stable"):
        held_back.append("The direction changes when a few years are dropped from either end.")
    if evidence.get("artifact_flag") is not False:
        held_back.append("A possible instrument effect could not be checked.")
    if not evidence.get("second_method_agrees"):
        held_back.append("A second trend method did not agree.")
    if evidence.get("independent_record_agrees") is not True:
        held_back.append("No independent record has been compared.")
    return ("significant", held_back) if held_back else ("robust", [])


def assess(finding: Finding, terminal: str) -> None:
    """Attach the claim. Refusals get none."""
    if terminal == "refusal":
        return
    conclusion = _conclusion(finding)
    if conclusion is None:
        # Weather playbooks: inference there is not calibrated, so every finding is descriptive.
        finding.claim = Claim(statement_type="descriptive_analysis", strength="descriptive", statement=WEATHER_STATEMENT)
        finding.would_strengthen.extend([
            "Calibrate the complete selected weather pipeline under seasonal, intermittent, persistent nulls.",
            "Review observing-system changes and compare spatially matched products with documented lineage.",
            "For discovery, validate selected signals on held-out data and control the full search family.",
        ])
        return
    strength, held_back = strength_for(conclusion.get("evidence", {}))
    statement = " ".join([conclusion["statement"], *conclusion.get("limits", []), CLOSING[strength]])
    finding.claim = Claim(statement_type=conclusion.get("statement_type", "descriptive_analysis"),
                          strength=strength, statement=statement)
    finding.would_strengthen.extend([*held_back, *conclusion.get("would_strengthen", [])])
