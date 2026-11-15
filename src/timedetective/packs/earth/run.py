"""Offline weather API and CLI. Questions are retained; intent/periods are explicit."""

import argparse
import json
import re
from pathlib import Path

import pandas as pd
import yaml

from timedetective.agent.report import render
from timedetective.engine.executor import execute
from timedetective.engine.models import Finding, Playbook
from timedetective.packs.earth import skills  # noqa: F401
from timedetective.packs.earth.adapters.power import load_power, PARAMETERS
from timedetective.packs.earth.adapters.csv import load_csv
from timedetective.skills.registry import get

ROOT = Path(__file__).resolve().parents[4]


def investigate(x: pd.Series, *, question: str, companion: pd.Series | None = None,
                intent: str = "seasonal", seasons: dict | None = None,
                baseline: tuple[int, int] = (2000, 2019), event: tuple[int, int] = (2020, 2022),
                root: Path = ROOT) -> Finding:
    """Run a declared investigation; never infer region or dates from a hoped-for answer."""
    unsupported = re.search(r"\b(forecast|predict|tomorrow|attribut\w*|caused|causes|causation|why|SPI|SPEI|return period|flood depth)\b", question, re.I)
    if unsupported:
        intent = f"unsupported_question:{unsupported.group(0)}"
    playbook = Playbook(**yaml.safe_load((root / "knowledge/playbooks/weather.yaml").read_text()))
    procedures = {p.stem: yaml.safe_load(p.read_text()) for p in (root / "knowledge/procedures").glob("*/*.yaml")}
    sources = yaml.safe_load((root / "knowledge/sources.yaml").read_text())
    context = {"intent": intent, "companion": companion,
               "seasons": seasons if seasons is not None else {"annual": list(range(1, 13))},
               "baseline_start": baseline[0], "baseline_end": baseline[1],
               "event_start": event[0], "event_end": event[1]}
    return execute(question, playbook, x, context, procedures, sources, get)


def discover(records: dict[str, pd.Series], *, seasons: dict, baseline: tuple[int, int],
             event: tuple[int, int]) -> dict:
    """Inspect every supplied location without choosing a region from its outcome.

    Retains the full search family; ranking is explicitly descriptive. No FDR is
    applied to empirical percentiles because those are not calibrated p-values.
    """
    findings = {key: investigate(series, question="Describe changes in all supplied locations",
                    intent="discovery", seasons=seasons, baseline=baseline, event=event)
                for key, series in records.items()}
    return {"search_family": list(records), "n_locations": len(records),
            "seasons": seasons, "baseline": baseline, "event": event,
            "scope": "all supplied records only; not global discovery; no inferential spatial claims",
            "findings": {key: value.model_dump(mode="json") for key, value in findings.items()}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--format", choices=["power", "csv"], default="power")
    parser.add_argument("--companion-data", type=Path, help="second CSV with its own provenance sidecar")
    parser.add_argument("--parameter", choices=PARAMETERS, default="PRECTOTCORR")
    parser.add_argument("--companion", choices=PARAMETERS)
    parser.add_argument("--question", required=True)
    parser.add_argument("--intent", default="seasonal",
                        help="seasonal, trend, discovery, extremes, weather; unsupported intents return a refusal")
    parser.add_argument("--seasons", default='{"annual":[1,2,3,4,5,6,7,8,9,10,11,12]}')
    parser.add_argument("--baseline", type=int, nargs=2, default=[2000, 2019])
    parser.add_argument("--event", type=int, nargs=2, default=[2020, 2022])
    parser.add_argument("--output", type=Path, required=True, help="new JSON path; existing evidence is not overwritten")
    args = parser.parse_args()
    x = load_power(args.data, args.parameter) if args.format == "power" else load_csv(args.data)
    y = (load_power(args.data, args.companion) if args.companion else None) if args.format == "power" else (
        load_csv(args.companion_data) if args.companion_data else None)
    finding = investigate(x, question=args.question, companion=y, intent=args.intent,
                          seasons=json.loads(args.seasons), baseline=tuple(args.baseline), event=tuple(args.event))
    report = args.output.with_suffix(".md")
    if args.output.exists() or report.exists():
        parser.error("output exists; choose new paths to preserve the evidence")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        handle.write(finding.model_dump_json(indent=2))
    with report.open("x") as handle:
        handle.write(render(finding))
    print(f"Wrote {args.output} and {report}")


if __name__ == "__main__":
    main()
