"""Evidence-only renderer. No model is required and no new scientific claims are invented."""

import json

from timedetective.engine.models import Finding


TITLES = {"season_check": "Season check", "water_storage_check": "Water storage check"}


def render(finding: Finding) -> str:
    lines = [f"# {TITLES.get(finding.playbook, 'Weather')} evidence report", "", finding.question, ""]
    if finding.claim:
        lines += [f"Claim strength: {finding.claim.strength}", "", finding.claim.statement, ""]
    else:
        lines += ["No scientific claim: required inputs or capabilities are missing.", ""]
    for step in finding.path:
        values = json.loads(step.values_json)
        if not isinstance(values.get("seasons"), dict):   # the weather playbooks' per-season summary
            continue
        lines += ["## Seasonal evidence at a glance", ""]
        for label, season in values["seasons"].items():
            lines += [f"{label}: event mean anomaly {season['event_mean_anomaly']:.2f} {season['unit']} "
                      f"relative to {season['baseline'][0]}–{season['baseline'][1]}; "
                      f"{season['event_below_threshold_count']} event seasons below the declared "
                      f"{100 * season['low_quantile']:g}th-percentile threshold. "
                      f"Evidence: {step.node}.seasons.{label}.", ""]
            long_term = season["long_term"]
            if long_term["status"] == "exploratory":
                lines += [f"Exploratory full-record Sen slope: {long_term['sen_slope_per_year']:.3f} "
                          f"{season['unit']} per year. Lowest iid-Gaussian BIC: {long_term['best_model']}. "
                          "These are descriptions, not proof of persistence or causation.", ""]
    for step in finding.path:
        values = json.loads(step.values_json)
        if "comparison" in values:
            lines += ["## Cross-product check", ""]
            for label, comparison in values["comparison"].items():
                lines += [f"{label}: primary anomaly {comparison['primary_event_anomaly']:.2f}; "
                          f"companion anomaly {comparison['companion_event_anomaly']:.2f}. "
                          f"Same sign: {comparison['same_anomaly_sign']}. Evidence: {step.node}.{label}.", ""]
            lines += [values["limitations"], ""]
    for subject in finding.subject:
        lines += [f"## Input: {subject.name}", "", subject.metadata_json, ""]
    for step in finding.path:
        lines += [f"## {step.node}: {step.procedure}", "",
                  f"Method: {step.source}; routing: {step.edge_source} ({step.edge_taken}).", "",
                  "```json", json.dumps(json.loads(step.values_json), indent=2), "```", ""]
    for refusal in finding.refusals:
        lines += [f"Refusal — {refusal.procedure}: {refusal.failed}. Needed: {refusal.would_change}.", ""]
    lines += ["## What would strengthen this", "", *[f"- {x}" for x in finding.would_strengthen]]
    references = {}
    for step in finding.path:
        references.update(json.loads(step.parameters_json).get("_references", {}))
    if references:
        lines += ["", "## References recorded with this run", ""]
        for key, ref in references.items():
            url = ref.get("url", "")
            title = ref.get("title", key)
            link = f"[{title}]({url})" if url.startswith("https://") else title
            lines.append(f"- {key}: {link}. Review: {ref.get('review', ref.get('kind', 'unspecified'))}.")
    return "\n".join(lines) + "\n"
