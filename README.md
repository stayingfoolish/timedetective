# timedetective

TimeDetective turns a plain-language question about a time series into a **Finding**: a typed answer with a claim-strength label (descriptive, significant or robust), the path of tests that produced it, and a citation for each step. It never claims more than the evidence supports.

Built for the NASA Space Apps *Earth System Trend Detective* challenge, on a core that is not specific to Earth data.

## Status

The weather evidence workflow is executable; broader inference remains unfinished.

**New:** [automatic precipitation investigator](docs/precipitation_investigator.md):
distill → NASA API → immutable cache → cited procedures → report. Includes dependent-data
trend/change experiments, SPI, conditional GEV return levels, spell/timing summaries and
cross-product family correction. **The new bootstrap inference failed the 5% dependence
calibration target; it is not certified statistical significance.** See
[validation](docs/precipitation_validation.md). The original offline weather workflow is preserved.

- **Done:** 53 existing statistical procedures plus six weather/metadata procedures; additive Finding/Playbook/Dataset models, a cited YAML executor, conservative critic, evidence-only renderer, two dataset cards, POWER and CSV adapters, an offline Streamlit form, and a real 2000–2024 NASA point cache (two precipitation products plus four weather variables). See [weather instructions](docs/weather_playbook.md) and [literature audit](docs/weather_literature.md).
- **Not done:** calibrated weather significance/robustness, matched regional native-product acquisition, inferential spatial discovery, arbitrary natural-language planning, attribution and forecasts. The four older general-purpose playbooks remain drafts in [docs/proposals/](docs/proposals/README.md).
- **Known failing check:** `make validate` reports 34 procedures whose `source` is still `TODO`. That is deliberate: those papers have not been opened yet.

The weather-only graph passes `uv run python scripts/validate_knowledge.py --scope weather`.
Weather Findings remain **descriptive**. Product disagreement is evidence, not a reason to
change the baseline or select a different location until a desired answer appears.

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
