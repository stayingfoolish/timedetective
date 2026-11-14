"""Validate everything in knowledge/ against schema/core.yaml.

Run with `make validate`. Exits non-zero on the first kind of problem found,
after printing every instance of it.
"""

import sys
from pathlib import Path

import yaml
from linkml.validator import validate

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schema" / "core.yaml"
KNOWLEDGE = ROOT / "knowledge"


def main() -> int:
    problems: list[str] = []
    sources = yaml.safe_load((KNOWLEDGE / "sources.yaml").read_text()) or {}

    procedures = sorted((KNOWLEDGE / "procedures").glob("*/*.yaml"))
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

    # Playbooks are validated here once the Playbook class exists in the schema.
    playbooks = sorted((KNOWLEDGE / "playbooks").glob("*.yaml"))
    if playbooks:
        problems.append("knowledge/playbooks/ has files but the schema has no Playbook class yet")

    for p in problems:
        print(f"FAIL  {p}")
    print(f"{len(procedures)} procedures, {len(sources)} sources, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
