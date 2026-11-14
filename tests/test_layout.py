"""The repo layout rules from AGENTS.md, as tests."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "src" / "timedetective"

LLM_IMPORT = re.compile(r"^\s*(?:import|from)\s+(anthropic|openai|litellm|langchain\w*)\b", re.M)
PACK_IMPORT = re.compile(r"^\s*(?:import|from)\s+timedetective\.packs\b", re.M)


def _categories() -> set[str]:
    schema = yaml.safe_load((ROOT / "schema" / "core.yaml").read_text())
    return set(schema["enums"]["SkillCategory"]["permissible_values"])


def _subfolders(path: Path) -> set[str]:
    return {p.name for p in path.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))}


def test_category_folders_match_the_schema():
    cats = _categories()
    assert _subfolders(PKG / "skills") == cats
    assert _subfolders(ROOT / "knowledge" / "procedures") == cats
    assert _subfolders(ROOT / "tests" / "skills") == cats


def test_no_llm_import_outside_agent():
    offenders = [
        str(p.relative_to(ROOT))
        for p in PKG.rglob("*.py")
        if "agent" not in p.relative_to(PKG).parts and LLM_IMPORT.search(p.read_text())
    ]
    assert offenders == []


def test_core_never_imports_a_pack():
    offenders = [
        str(p.relative_to(ROOT))
        for p in PKG.rglob("*.py")
        if "packs" not in p.relative_to(PKG).parts and PACK_IMPORT.search(p.read_text())
    ]
    assert offenders == []
