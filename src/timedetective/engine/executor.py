"""Execute cited, acyclic playbook data. No domain imports or model calls."""

import json
import hashlib
from collections.abc import Callable
from typing import Any

import pandas as pd

from timedetective.engine.critic import assess
from timedetective.engine.models import Finding, FindingRefusal, Playbook, SeriesRef, Step
from timedetective.skills.result import SkillResult


def encode(value: Any) -> str:
    """Strict JSON: never silently serialize NaN, Infinity, or unknown objects."""
    return json.dumps(value, sort_keys=True, allow_nan=False)


def validate_graph(playbook: Playbook, procedures: dict, sources: dict) -> None:
    nodes = {n.id: n for n in playbook.nodes}
    if len(nodes) != len(playbook.nodes) or playbook.start not in nodes:
        raise ValueError("duplicate node or invalid start")
    edge_ids = [e.id for e in playbook.edges]
    if len(set(edge_ids)) != len(edge_ids):
        raise ValueError("duplicate edge id")
    for edge in playbook.edges:
        if edge.origin not in nodes or edge.target not in nodes:
            raise ValueError("edge references missing node")
        if edge.source not in sources or edge.source == "TODO":
            raise ValueError("uncited edge")
        if edge.domain != playbook.domain or edge.outcome not in {"ok", "refused", "always"}:
            raise ValueError("invalid edge domain or outcome")
    for node in nodes.values():
        edges = [e for e in playbook.edges if e.origin == node.id]
        if node.terminal:
            if node.terminal not in {"claim", "refusal"} or edges or node.procedure:
                raise ValueError("invalid terminal")
        else:
            if node.procedure not in procedures:
                raise ValueError(f"unknown procedure {node.procedure}")
            source = procedures[node.procedure].get("source")
            if source not in sources or source == "TODO":
                raise ValueError(f"uncited procedure {node.procedure}")
            outcomes = sorted(e.outcome for e in edges)
            if outcomes not in [["always"], ["ok", "refused"]]:
                raise ValueError(f"non-exhaustive or ambiguous routing at {node.id}")
            if not isinstance(json.loads(node.parameters_json or "{}"), dict):
                raise ValueError("parameters must be a JSON object")
    seen, active = set(), set()

    def walk(node_id: str) -> None:
        if node_id in active:
            raise ValueError("cyclic playbook")
        if node_id in seen:
            return
        active.add(node_id)
        for edge in playbook.edges:
            if edge.origin == node_id:
                walk(edge.target)
        active.remove(node_id)
        seen.add(node_id)

    walk(playbook.start)
    if seen != set(nodes):
        raise ValueError("unreachable nodes")


def execute(question: str, playbook: Playbook, x: pd.Series, context: dict,
            procedures: dict, sources: dict, lookup: Callable[[str], Callable]) -> Finding:
    """Every successful step or failed precondition is retained, including citations."""
    validate_graph(playbook, procedures, sources)
    contract = {"playbook_sha256": hashlib.sha256(encode(playbook.model_dump(mode="json")).encode()).hexdigest(),
                "sources_sha256": hashlib.sha256(encode(sources).encode()).hexdigest()}
    finding = Finding(schema_version="0.1", question=question, playbook=playbook.name,
                      subject=[], path=[], refusals=[], would_strengthen=[])
    for series in [x, context.get("companion")]:
        if series is None:
            continue
        meta = series.attrs
        if all(k in meta for k in ("units", "cadence", "source", "retrieved")):
            try:
                finding.subject.append(SeriesRef(name=str(series.name), units=meta["units"],
                    cadence=meta["cadence"], source=meta["source"], retrieved=meta["retrieved"],
                    metadata_json=encode(meta)))
            except (ValueError, TypeError):
                # The cited audit step reports the invalid metadata as a refusal.
                pass
    state = {"x": x, **context}
    nodes = {n.id: n for n in playbook.nodes}
    current = playbook.start
    while not nodes[current].terminal:
        node = nodes[current]
        spec = json.loads(node.parameters_json or "{}")
        params = {}
        try:
            params = {k: state[v[1:]] if isinstance(v, str) and v.startswith("$") else v
                      for k, v in spec.items()}
            result: SkillResult = lookup(node.procedure)(state[node.input or "x"], **params)
        except (KeyError, ValueError, TypeError) as exc:
            # Configuration/data contract failures are visible; programming errors of other
            # kinds still fail tests rather than being disguised as scientific refusals.
            from timedetective.skills.result import refuse
            result = refuse(node.procedure, f"input contract: {exc}", "supply valid inputs and parameters")
        edges = [e for e in playbook.edges if e.origin == current and
                 e.outcome in ("always", "ok" if result.ok else "refused")]
        edge = edges[0]
        resolved = {k: ({"series": str(v.name), "sha256": v.attrs.get("sha256")} if isinstance(v, pd.Series) else v)
                    for k, v in params.items()}
        keys = {procedures[node.procedure]["source"], edge.source, *result.values.get("method_sources", [])}
        resolved["_references"] = {key: sources[key] for key in sorted(keys)}
        resolved["_run_contract"] = contract
        finding.path.append(Step(node=current, procedure=node.procedure,
            parameters_json=encode(resolved), values_json=encode(result.values),
            source=procedures[node.procedure]["source"], edge_taken=edge.id, edge_source=edge.source))
        if result.refusal:
            finding.refusals.append(FindingRefusal(**vars(result.refusal)))
        for subrefusal in result.values.get("subprocedure_refusals", []):
            finding.refusals.append(FindingRefusal(**subrefusal))
        if result.series is not None:
            state[current] = result.series
        state[f"{current}_values"] = result.values
        for key, value in result.values.items():
            state[f"{current}.{key}"] = value
        current = edge.target
    if nodes[current].terminal == "refusal" and not finding.refusals:
        finding.refusals.append(FindingRefusal(procedure="executor", failed="refusal terminal",
            would_change="satisfy the playbook preconditions"))
    assess(finding, terminal=nodes[current].terminal)
    return finding
