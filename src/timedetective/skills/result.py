"""What every skill returns: values, optionally a new series, or a refusal.

This is the skill-level return convention, not the Finding. The engine turns
SkillResults into Finding fields; a Refusal maps onto `finding.refusals`.
"""

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class Refusal:
    """A precondition failed: what failed, and what would change it."""

    procedure: str
    failed: str
    would_change: str


@dataclass(frozen=True)
class SkillResult:
    """Outcome of one procedure. Exactly one of `refusal` or a result is set."""

    procedure: str
    values: dict[str, Any] = field(default_factory=dict)
    series: pd.Series | None = None
    refusal: Refusal | None = None

    @property
    def ok(self) -> bool:
        return self.refusal is None


def refuse(procedure: str, failed: str, would_change: str) -> SkillResult:
    """Build a refused SkillResult."""
    return SkillResult(procedure, refusal=Refusal(procedure, failed, would_change))
