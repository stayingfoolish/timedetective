# AGENTS.md

Instructions for AI coding agents working in this repo. Read this before changing anything.

## What this project is

TimeDetective turns a plain-language question about a time series into a Finding: a typed answer with a claim-strength label, the path of tests that produced it, and a citation for each step. It never claims more than the evidence supports.

Three layers:

- **Ontology** (`schema/`, `knowledge/`): what the system knows. LinkML schema plus YAML instances for procedures and playbooks.
- **Skills** (`src/timedetective/skills/`): what the system can do. Deterministic functions, one per procedure.
- **Agent loop** (`src/timedetective/engine/`, `src/timedetective/agent/`): how it decides. Executor walks a playbook, critic checks every step, planner and narrator are the only LLM calls.

## Rules that must never be broken

These are the product. A change that violates one is wrong even if the tests pass.

1. **No LLM outside `agent/`.** `skills/`, `engine/` and `packs/` never import an LLM client or call a model.
2. **Skills are deterministic and pure.** Same input, same output. No network, no file writes, no randomness without an explicit seed argument.
3. **The core never imports a pack.** `packs/*` may import from `skills/` and `engine/`; the reverse is forbidden.
4. **Playbooks are data.** Analysis order lives in `knowledge/playbooks/*.yaml`, never in Python control flow. If you are writing `if autocorrelated: prewhiten()` in the executor, stop.
5. **Only the critic sets `claim.strength`.** No skill, prompt or narrator code assigns or upgrades it.
6. **The narrator says only what the Finding contains.** Every number and claim in narrated text must trace to a Finding field.
7. **Every playbook edge and every procedure has a `source`.** Never invent a citation. If you do not have the real paper, leave `source: TODO` and say so in your summary; the validator will flag it.
8. **Refusals are results.** When a precondition fails, record it in `finding.refusals` with what failed and what would change it. Do not raise, skip, or silently fall back.
9. **Do not edit `schema/generated/`.** Change `schema/core.yaml` and regenerate.
10. **Do not change the Finding schema without being asked.** Adding an optional field is allowed if requested; renaming or removing one is a breaking change that needs a `schema_version` bump and human sign-off.

## Commands

```bash
uv sync                      # install
make validate                # LinkML-validate everything in knowledge/
make generate                # regenerate schema/generated/ from schema/core.yaml
make test                    # all fast tests, including the layout rules in tests/test_layout.py
uv run pytest tests/skills   # known-answer tests for skills
uv run pytest tests/engine   # critic and executor behavior
make calibrate               # false-positive rate on trend-free series (slow)
make demo                    # Streamlit demo
```

Run `make validate` and the relevant `pytest` folder before saying a task is done. Report what you ran and what failed.

Dependencies are managed only with uv: `uv add <package>` (or `uv add --dev`), never `pip install`. Commit `pyproject.toml` and `uv.lock` together. Run tools through `uv run`. Human setup, including the VS Code notebook kernel, is in [CONTRIBUTING.md](CONTRIBUTING.md).

Notebooks in `notebooks/` are for exploration only. Do not put logic there that is not also in `src/` with a test, and do not edit a notebook you were not asked to edit.

## How to add things

**A skill**

Skills live in one subfolder per skill type. The folder name equals the procedure's `category` in the ontology:

| Folder | What belongs there | Examples |
| --- | --- | --- |
| `diagnostics/` | Measures a property of a series; changes nothing | lag-1 autocorrelation, stationarity, seasonality strength, gaps, record length |
| `transforms/` | Returns a new series | deseasonalize, prewhiten, difference, resample, gap-fill |
| `trend/` | Tests for and sizes a monotonic change | Mann-Kendall, Sen's slope, seasonal Mann-Kendall |
| `changepoint/` | Finds when behavior changed | break detection, segment comparison |
| `relationship/` | Relates two or more series | cross-correlation, Granger, cointegration |
| `detectability/` | Says what this record is able to show | minimum detectable trend, time of emergence |
| `robustness/` | Re-tests a result another way | second method, sub-period, independent record, field significance |

1. Add the procedure to `knowledge/procedures/<category>/<name>.yaml` with `category`, `requires`, `produces`, `source`.
2. Implement the function in `src/timedetective/skills/<category>/`, with a typed signature matching that YAML. One file per procedure or closely related pair.
3. Register it in `skills/registry.py` under the same name as the YAML.
4. Add a known-answer test in `tests/skills/<category>/` using a generator from `data/synthetic/`: one series where the effect is present, one where it is absent.

Do not create a new category folder without asking; a new category is a schema change (it adds a value to the `category` enum). Domain-specific skills go in their pack (`packs/<pack>/skills/<category>/`), not here.

**A playbook**

1. Add `knowledge/playbooks/<name>.yaml`: nodes name procedures, edges name a condition on a property, a `domain`, and a `source`.
2. Every path must end in a claim-strength assignment or a refusal.
3. Add one end-to-end test in `tests/engine/` that walks it on synthetic data.
4. No Python changes should be needed. If they are, say why before making them.

**A data adapter**

1. Put it in the right pack under `src/timedetective/packs/<pack>/`.
2. Return a typed `Series` with units, cadence, source and retrieval date.
3. Tests read from `data/cache/`, never from the network.

## Statistical correctness

- Prefer a well-tested library implementation over writing a test statistic from scratch. If you write one, cite the formula's source in the docstring and test it against a published or library value.
- Always handle: missing values, irregular spacing, ties, series shorter than the method's minimum. Each should produce a refusal, not an exception or a silent result.
- Never loosen a threshold, drop a correction, or change a null model to make a test pass or a result look stronger. If calibration fails, report it.
- The calibration target is a false-positive rate at or below 5% on trend-free series with realistic autocorrelation. Changes to `skills/` or `engine/critic.py` should rerun it.

## Data

- `data/cache/` holds the exact series the demo uses, committed, each with a note of source and retrieval date. Do not overwrite these.
- Do not add files over a few MB, credentials, or API keys. Keys come from environment variables.
- Do not guess data-provider APIs. If an adapter needs an endpoint you have not been shown, ask.

## Style

- Python 3.11+, type hints everywhere, pydantic models generated from the schema.
- Small functions, no classes where a function will do.
- Docstrings state what the procedure assumes and what it returns, in one or two lines.
- No new dependencies without asking.

## When unsure

Ask before: changing the schema, adding a dependency, touching `data/cache/`, or changing anything in `engine/critic.py`. For everything else, make the smallest change that satisfies the request and state your assumptions in the summary.
