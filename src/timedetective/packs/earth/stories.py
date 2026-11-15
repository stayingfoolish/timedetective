"""Run the season check and the water storage check. Information only; no model calls.

Each function takes series that already carry provenance (from an adapter), runs the
loaded playbook through the core executor and returns a Finding. Nothing here chooses
a place, a season or a period from the result.
"""

import re
from pathlib import Path

import pandas as pd
import yaml

from timedetective.engine.executor import execute
from timedetective.engine.models import Finding, Playbook
from timedetective.packs.earth import skills  # noqa: F401
from timedetective.skills.registry import get

ROOT = Path(__file__).resolve().parents[4]

# Parts of a question these checks do not answer. The check still runs; the finding says what was left out.
BEYOND = [
    (re.compile(r"\b(why|because|caus\w*|due to|blame|pumping|irrigation|climate change)\b", re.I),
     "The question asks about a cause; this check does not identify causes."),
    (re.compile(r"\b(forecast|predict\w*|will|next (year|season|month)|going to|how long|run out|last)\b", re.I),
     "The question asks about the future; this check describes the record so far and makes no forecast."),
    (re.compile(r"\b(fail\w*|declare|emergency|famine|yield|harvest|should (we|i))\b", re.I),
     "The question asks for a judgement about a harvest or a decision; this check supplies information for people to weigh, not a declaration."),
]


def not_answered(question: str) -> list[str]:
    return [note for pattern, note in BEYOND if pattern.search(question)]


def _run(name: str, question: str, x: pd.Series, context: dict, root: Path) -> Finding:
    playbook = Playbook(**yaml.safe_load((root / f"knowledge/playbooks/{name}.yaml").read_text()))
    procedures = {p.stem: yaml.safe_load(p.read_text()) for p in (root / "knowledge/procedures").glob("*/*.yaml")}
    sources = yaml.safe_load((root / "knowledge/sources.yaml").read_text())
    return execute(question, playbook, x, {**context, "not_answered": not_answered(question)}, procedures, sources, get)


def check_season(vegetation: pd.Series, *, question: str, season_months: list[int], target_year: int,
                 rainfall: pd.Series | None = None, lead_months: int = 1, root: Path = ROOT) -> Finding:
    """How unusual is the vegetation reading in a declared season, against the same place's own record?

    The season months are declared by the user for the place; they are not inferred. With a
    rainfall record the finding reports whether a second indicator agrees; without one it
    stands on vegetation alone and says so.
    """
    return _run("season_check", question, vegetation, {
        "season_months": list(season_months), "target_year": target_year, "rainfall": rainfall,
        "companion": rainfall, "lead_months": lead_months}, root)


def check_storage(storage: pd.Series, *, question: str, rainfall: pd.Series | None = None,
                  soil_wetness: pd.Series | None = None, gap: tuple[str, str] = ("2017-07-01", "2018-05-31"),
                  root: Path = ROOT) -> Finding:
    """Is the water stored in and under a region changing, and does the change follow rainfall?

    `gap` is the period between the two satellite missions, from the dataset card.
    """
    return _run("water_storage_check", question, storage, {
        "rainfall": rainfall, "companion": rainfall, "soil_wetness": soil_wetness,
        "gap_start": gap[0], "gap_end": gap[1]}, root)


def check_storage_and_greenness(storage: pd.Series, *, question: str, vegetation: pd.Series | None,
                                rainfall: pd.Series | None = None, soil_wetness: pd.Series | None = None,
                                gap: tuple[str, str] = ("2017-07-01", "2018-05-31"), root: Path = ROOT) -> Finding:
    """The water storage check, then the region's greenness set beside it over the same years.

    Answers "would the fields show it?": whether greenness held, rose or fell while storage
    changed. The vegetation record must cover the same region as the storage record.
    """
    return _run("water_and_greenness_check", question, storage, {
        "rainfall": rainfall, "companion": rainfall, "soil_wetness": soil_wetness, "vegetation": vegetation,
        "gap_start": gap[0], "gap_end": gap[1]}, root)
