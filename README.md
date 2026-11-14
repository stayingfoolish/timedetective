# timedetective

TimeDetective turns a plain-language question about a time series into a **Finding**: a typed answer with a claim-strength label (descriptive, significant or robust), the path of tests that produced it, and a citation for each step. It never claims more than the evidence supports.

Built for the NASA Space Apps *Earth System Trend Detective* challenge, on a core that is not specific to Earth data.

## Status

Skeleton only. The layout, tooling and rules are in place; skills, playbooks and the Finding schema are not written yet.

## Quickstart

```bash
uv sync
make validate
make test
```

## Layout

```
schema/        LinkML schema, the source of truth
knowledge/     procedures, playbooks and sources as YAML (no Python)
src/timedetective/
  skills/      deterministic functions, one subfolder per skill type
  engine/      executor, critic, state
  agent/       planner and narrator: the only LLM calls
  packs/       domain-specific adapters and skills (earth, retail)
data/          cache/ (committed demo series), synthetic/
tests/         skills/, engine/, knowledge/, calibration/
notebooks/     exploration only
app/           demo
extractor/     literature extractor (stub)
```

## Developing

- [CONTRIBUTING.md](CONTRIBUTING.md): setup, dependencies with uv, notebooks in VS Code, the daily loop.
- [AGENTS.md](AGENTS.md): the rules that must never be broken, and how to add a skill, a playbook or a data adapter.

## License

MIT
