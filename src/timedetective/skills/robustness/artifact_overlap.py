"""Compare candidate boundary years with dated metadata; never prove an artifact."""

import pandas as pd

from timedetective.skills.registry import register
from timedetective.skills.result import SkillResult, refuse


@register("artifact_overlap")
def artifact_overlap(x: pd.Series, candidate_years: list[int], tolerance_years: int = 1) -> SkillResult:
    """Metadata coincidence screen, with explicit year-resolution tolerance (house rule)."""
    name = "artifact_overlap"
    if not isinstance(tolerance_years, int) or tolerance_years < 0:
        return refuse(name, "invalid tolerance", "provide a nonnegative integer tolerance in years")
    dated = [issue for issue in x.attrs.get("known_issues", [])
             if isinstance(issue, dict) and issue.get("start") and issue.get("source")]
    if not dated:
        return refuse(name, "no cited dated observing history", "provide dated sensor, station, algorithm or assimilation history; absence of metadata is not evidence of homogeneity")
    matches = []
    for year in candidate_years:
        for issue in dated:
            start = pd.Timestamp(issue["start"]).year
            end = pd.Timestamp(issue.get("end", issue["start"])).year
            if start - tolerance_years <= year <= end + tolerance_years:
                matches.append({"candidate_year": year, "issue": issue})
    return SkillResult(name, {"candidate_years": candidate_years, "tolerance_years": tolerance_years,
        "coincidences": matches, "reviewed_dated_issues": len(dated),
        "interpretation": "coincidence warrants investigation; neither a match nor its absence establishes measurement artifact or environmental cause"})
