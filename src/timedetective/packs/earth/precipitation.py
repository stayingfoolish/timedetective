"""Distill → acquire → cited YAML analysis → cross-product family → reproducible report."""

import argparse
from datetime import date
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys

import pandas as pd
import yaml

from timedetective.agent.precipitation import PrecipitationRequest, distill
from timedetective.agent.report import render
from timedetective.engine.executor import execute
from timedetective.engine.models import Finding, FindingRefusal, Playbook
from timedetective.skills.registry import get
from . import skills  # noqa: F401
from .adapters.power_api import STARTS, fetch_power

ROOT = Path(__file__).resolve().parents[4]


def refusal(question: str, procedure: str, error: str, needed: str) -> Finding:
    return Finding(schema_version="0.1", question=question, playbook="precipitation", subject=[], path=[],
        refusals=[FindingRefusal(procedure=procedure, failed=error, would_change=needed)], would_strengthen=[])


def run_request(request: PrecipitationRequest, *, cache_dir: Path, offline: bool = False,
                records: dict[str, pd.Series] | None = None) -> dict:
    """Run both products without substituting or silently discarding a failed product.

    records is an explicit offline API for previously validated adapters. No network
    is called in that mode. Acquisition failures become Findings, not fake series.
    """
    # Revalidate even model_construct/model_copy callers; bounds precede network activity.
    request = distill(**request.model_dump(mode="json"))
    sources = yaml.safe_load((ROOT / "knowledge/sources.yaml").read_text())
    procedures = {p.stem: yaml.safe_load(p.read_text()) for p in (ROOT / "knowledge/procedures").glob("*/*.yaml")}
    playbook = Playbook(**yaml.safe_load((ROOT / "knowledge/playbooks/precipitation.yaml").read_text()))
    series, findings, coverage = {}, {}, {}
    for product in request.products:
        # Retain the full MERRA record; do not silently claim pre-launch IMERG observations.
        actual_start = max(request.start, STARTS[product])
        coverage[product] = {"requested_start": str(request.start), "provider_start": str(actual_start),
            "end": str(request.end), "precoverage_unavailable": actual_start != request.start}
        try:
            x = records[product] if records is not None else fetch_power(latitude=request.latitude,
                longitude=request.longitude, start=actual_start, end=request.end,
                parameter=product, cache_dir=cache_dir, offline=offline)
            support = x.attrs.get("spatial_support", {})
            if support.get("kind") != "point_query" or support.get("latitude") != request.latitude or support.get("longitude") != request.longitude:
                raise ValueError("record spatial support differs from distilled point")
            if x.attrs.get("variable") != "precipitation":
                raise ValueError("record is not precipitation")
            # Slicing is explicit and retains the original raw checksum and acquisition metadata.
            x = x.loc[str(actual_start):str(request.end)].copy()
            if len(x) < 2:
                raise ValueError("no observations in requested period")
            if not x.index.equals(pd.date_range(actual_start, request.end, freq="D")):
                raise ValueError("record does not contain every requested daily timestamp")
            x.attrs["analysis_request"] = request.model_dump(mode="json")
            x.attrs["coverage"] = coverage[product]
            series[product] = x
        except (OSError, ValueError, KeyError, TypeError) as exc:
            findings[product] = refusal(request.question, "precipitation_acquisition", str(exc),
                "resolve coordinates/dates, provider response, connectivity or immutable cache; no substitute data were used")
    families = {}
    declared_count = len(request.seasons) * sum(a in request.analyses for a in ["trend", "period_change", "changepoint"])
    context = request.model_dump(mode="json")
    context.update(baseline_start=request.baseline[0], baseline_end=request.baseline[1],
                   event_start=request.event[0], event_end=request.event[1], declared_tests=declared_count)
    for product, x in series.items():
        companions = [v for k, v in series.items() if k != product]
        findings[product] = execute(request.question, playbook, x,
            {**context, "companion": companions[0] if companions else None}, procedures, sources, get)
        step = next((s for s in findings[product].path if s.node == "family"), None)
        if step:
            families[product] = json.loads(step.values_json)
    for product in request.products:
        if product not in families:
            families[product] = {"tests": [], "failed_members": declared_count}
    global_finding = None
    if series:
        global_book = Playbook(**yaml.safe_load((ROOT / "knowledge/playbooks/precipitation_family.yaml").read_text()))
        global_finding = execute(request.question, global_book, next(iter(series.values())),
            {"families": families, "alpha": request.alpha}, procedures, sources, get)
    fingerprints = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted((ROOT / "src/timedetective").rglob("*.py"))}
    return {"schema_version": "precipitation-run-1", "request": request.model_dump(mode="json"),
        "runtime": {"python": sys.version.split()[0], **{p:version(p) for p in ["numpy","pandas","scipy","statsmodels","pydantic"]}},
        "implementation_sha256": fingerprints,
        "coverage": coverage, "findings": {k: findings[k].model_dump(mode="json") for k in request.products},
        "global_family": global_finding.model_dump(mode="json") if global_finding else None,
        "limitations": ["Point-query gridded precipitation, not polygon means or gauge observations.",
            "Distillation uses bounded keyword routing and explicit controls; inspect the request before accepting an answer.",
            "Bootstrap decisions are experimental; SPI and GEV estimates are conditional on their models, not universally calibrated.",
            "Shared inputs mean MERRA-2/IMERG agreement is not independent replication."]}


def investigate_question(question: str, *, cache_dir: Path, offline: bool = False,
                         records: dict[str, pd.Series] | None = None, **controls: object) -> dict:
    """Public entry point: invalid distillation yields refusal without any API call."""
    try:
        request = distill(question, **controls)
    except (ValueError, TypeError) as exc:
        finding = refusal(question, "precipitation_distillation", str(exc),
            "supply an explicit point, complete-year dates, baseline/event, seasons and supported historical precipitation analyses")
        return {"schema_version": "precipitation-run-1", "request": None,
                "findings": {"distillation": finding.model_dump(mode="json")}, "global_family": None}
    return run_request(request, cache_dir=cache_dir, offline=offline, records=records)


def render_run(bundle: dict) -> str:
    """Every sentence/number is taken from the request or a recorded Finding."""
    lines = ["# Precipitation investigation", "", "## Distilled request", "",
        "```json", json.dumps(bundle["request"], indent=2), "```", ""]
    if bundle.get("global_family"):
        global_finding = Finding(**bundle["global_family"])
        for step in global_finding.path:
            evidence = json.loads(step.values_json)
            if not evidence:
                continue
            lines += ["## Statistical tests across both products", "", evidence["interpretation"], ""]
            for test in evidence["tests"]:
                lines += [f"- {test['product']} / {test['id']}: estimate {test['estimate']:.4g}; "
                    f"global Holm-adjusted p={test['p_holm_global']:.4g}; status: {test['inference_status']}."]
        lines += ["", render(global_finding)]
    for product, content in bundle["findings"].items():
        lines += ["", f"# Product: {product}", "", render(Finding(**content))]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", required=True)
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--longitude", type=float, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--baseline", type=int, nargs=2, required=True)
    parser.add_argument("--event", type=int, nargs=2, required=True)
    parser.add_argument("--seasons", default='{"annual":[1,2,3,4,5,6,7,8,9,10,11,12]}')
    parser.add_argument("--analyses", nargs="+")
    parser.add_argument("--target", choices=["seasonal_total", "rx1day", "rx5day", "wet_days", "dry_spell", "sdii"])
    parser.add_argument("--timing-windows", help='JSON broad windows, e.g. {"wet":["02-01","06-30"]}')
    parser.add_argument("--cache-dir", type=Path, default=Path("downloads/power"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--preview", action="store_true", help="distill and print the contract; never access the network")
    parser.add_argument("--output", type=Path, help="new output directory; never overwrite prior evidence")
    args = vars(parser.parse_args())
    cache_dir, offline, preview, output = [args.pop(k) for k in ["cache_dir", "offline", "preview", "output"]]
    args["seasons"] = json.loads(args["seasons"])
    args["timing_windows"] = json.loads(args["timing_windows"]) if args["timing_windows"] else None
    if args["target"] is None:
        args.pop("target")
    if preview:
        try:
            print(distill(**args).model_dump_json(indent=2))
        except ValueError as exc:
            parser.error(str(exc))
        return
    if output is None or output.exists():
        parser.error("--output must name a new directory")
    bundle = investigate_question(**args, cache_dir=cache_dir, offline=offline)
    output.mkdir(parents=True, exist_ok=False)
    (output / "investigation.json").write_text(json.dumps(bundle, indent=2, allow_nan=False))
    (output / "report.md").write_text(render_run(bundle))
    print(f"Wrote {output / 'report.md'}")


if __name__ == "__main__":
    main()
