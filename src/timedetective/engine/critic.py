"""Only this module assigns claim strength; weather inference is not yet calibrated."""

from timedetective.engine.models import Claim, Finding


def assess(finding: Finding, terminal: str) -> None:
    """Do not transfer the legacy AR(1) calibration to seasonal weather or discovery."""
    if terminal == "refusal":
        return
    finding.claim = Claim(statement_type="descriptive_analysis", strength="descriptive",
        statement="The recorded calculations describe the supplied data and spatial support. "
        "They do not establish a permanent climate change, cause, forecast, or absence of change.")
    finding.would_strengthen.extend([
        "Calibrate the complete selected weather pipeline under seasonal, intermittent, persistent nulls.",
        "Review observing-system changes and compare spatially matched products with documented lineage.",
        "For discovery, validate selected signals on held-out data and control the full search family.",
    ])
