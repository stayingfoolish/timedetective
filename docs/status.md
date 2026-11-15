# Project status and developer notes

Moved here from the README so the front page can speak to first-time readers. Paths are relative to the repository root.

## Status

The weather evidence workflow is executable; broader inference remains unfinished.

**New:** [automatic precipitation investigator](precipitation_investigator.md):
distill → NASA API → immutable cache → cited procedures → report. Includes dependent-data
trend/change experiments, SPI, conditional GEV return levels, spell/timing summaries and
cross-product family correction. **The new bootstrap inference failed the 5% dependence
calibration target; it is not certified statistical significance.** See
[validation](precipitation_validation.md). The original offline weather workflow is preserved.

- **Done:** general-purpose statistical procedures across the seven skill categories plus weather procedures in the earth pack; Finding/Playbook/Dataset models, a cited YAML executor, an evidence-based critic, an evidence-only renderer, POWER and CSV adapters, an offline Streamlit form, and a real 2000–2024 NASA point cache. See [weather instructions](weather_playbook.md), [literature audit](weather_literature.md) and [calibration](calibration.md).
- **Done, two story checks:** a season check (how unusual is this growing season here?) and a water storage check (is the water stored under this region changing, and does it follow rainfall?), each a loaded, cited playbook with known-answer tests and a calibrated claim rule. Information only: no forecasts, causes or declarations. See [story playbooks](story_playbooks.md). Real NASA records and results for Karamoja, north-west India and the US High Plains are in `data/cache/earth/stories/` and [story_results.md](story_results.md).
- **Not done:** calibrated weather significance/robustness, matched regional native-product acquisition, inferential spatial discovery, arbitrary natural-language planning, attribution and forecasts. For the story checks: the GLDAS subtraction that turns total water storage into groundwater (needs an Earthdata login), an independent record such as wells, a cropland mask, and a second vegetation sensor. Six general-purpose playbooks remain drafts in [docs/proposals/](proposals/README.md).
- **Known failing check:** `make validate` reports procedures whose `source` is still `TODO`. That is deliberate: those papers have not been opened yet. `--scope weather` and `--scope stories` are clean.

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

- [CONTRIBUTING.md](../CONTRIBUTING.md): setup, dependencies with uv, notebooks in VS Code, the daily loop.
- [AGENTS.md](../AGENTS.md): the rules that must never be broken, and how to add a skill, a playbook or a data adapter.
