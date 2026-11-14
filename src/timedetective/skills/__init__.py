"""Deterministic skills, one per procedure. Importing this package registers all of them."""

from timedetective.skills import (  # noqa: F401
    changepoint,
    detectability,
    diagnostics,
    relationship,
    robustness,
    transforms,
    trend,
)
