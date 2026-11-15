"""Validate everything in knowledge/ against schema/core.yaml.

Run with `make validate`. Exits non-zero on the first kind of problem found,
after printing every instance of it.
"""

import sys
import argparse
from pathlib import Path

import yaml
from linkml.validator import validate

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schema" / "core.yaml"
KNOWLEDGE = ROOT / "knowledge"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=["all", "weather"], default="all")
    args = parser.parse_args()
    problems: list[str] = []
    sources = yaml.safe_load((KNOWLEDGE / "sources.yaml").read_text()) or {}

    procedures = sorted((KNOWLEDGE / "procedures").glob("*/*.yaml"))
    if args.scope == "weather":
        procedures = [p for p in procedures if p.stem.startswith("weather_") or p.stem == "artifact_overlap"]
    for path in procedures:
        rel = path.relative_to(ROOT)
        data = yaml.safe_load(path.read_text())
        report = validate(data, str(SCHEMA), "Procedure")
        problems += [f"{rel}: {r.message}" for r in report.results]
        if not isinstance(data, dict):
            continue
        if data.get("name") != path.stem:
            problems.append(f"{rel}: name must equal the file name ({path.stem})")
        if data.get("category") != path.parent.name:
            problems.append(f"{rel}: category must equal the folder ({path.parent.name})")
        source = data.get("source")
        if source == "TODO":
            problems.append(f"{rel}: source is still TODO")
        elif source and source not in sources:
            problems.append(f"{rel}: source '{source}' is not in knowledge/sources.yaml")

    from timedetective.engine.executor import validate_graph
    from timedetective.engine.models import Playbook
    definitions = {p.stem: yaml.safe_load(p.read_text()) for p in (KNOWLEDGE / "procedures").glob("*/*.yaml")}
    playbooks = sorted((KNOWLEDGE / "playbooks").glob("*.yaml"))
    for path in playbooks:
        data = yaml.safe_load(path.read_text())
        report = validate(data, str(SCHEMA), "Playbook")
        problems += [f"{path.relative_to(ROOT)}: {r.message}" for r in report.results]
        try:
            if data["name"] != path.stem:
                raise ValueError("name differs from file")
            validate_graph(Playbook(**data), definitions, sources)
        except (ValueError, TypeError, KeyError) as exc:
            problems.append(f"{path.relative_to(ROOT)}: {exc}")
    for path in sorted((KNOWLEDGE / "datasets").glob("*/*.yaml")):
        data = yaml.safe_load(path.read_text())
        report = validate(data, str(SCHEMA), "Dataset")
        problems += [f"{path.relative_to(ROOT)}: {r.message}" for r in report.results]
        if data.get("name") != path.stem or data.get("pack") != path.parent.name:
            problems.append(f"{path}: name or pack mismatch")
        for source in [data.get("source"), *[issue.get("source") for issue in data.get("known_issues", [])]]:
            if source not in sources or source == "TODO":
                problems.append(f"{path}: unresolved source {source}")

    for p in problems:
        print(f"FAIL  {p}")
    print(f"scope={args.scope}: {len(procedures)} procedures, {len(playbooks)} playbooks, {len(sources)} sources, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
