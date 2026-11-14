# Developing TimeDetective

Short on purpose. If something here is wrong, fix it in the same commit that proves it wrong.

## 1. Setup (once)

Requires [uv](https://docs.astral.sh/uv/) and VS Code with the Python and Jupyter extensions.

```bash
git clone <repo-url> && cd timedetective
uv sync                # creates .venv/ and installs everything from uv.lock
cp .env.example .env   # add your LLM API key; .env is gitignored
make validate          # should pass on a fresh clone
```

`uv sync` installs the project itself in editable mode, so `import timedetective` always reflects your working tree.

## 2. Dependencies

uv is the only way dependencies change. Never `pip install` into the environment; it will not be recorded and your teammate's machine will break.

| To do this | Run |
| --- | --- |
| Add a runtime dependency | `uv add <package>` |
| Add a dev-only tool (pytest, ipykernel, ruff) | `uv add --dev <package>` |
| Remove one | `uv remove <package>` |
| Get in sync after pulling | `uv sync` |
| Run anything in the environment | `uv run <command>` |

- `pyproject.toml` lists what we asked for; `uv.lock` pins exactly what was installed. Commit both, together, in the same commit as the code that needs the change.
- After `git pull`, if `uv.lock` changed, run `uv sync` before anything else.
- Python version is pinned in `.python-version`. uv downloads it if you do not have it.
- Keep the list short. Prefer numpy, pandas, scipy, statsmodels and pymannkendall over anything new.

## 3. Notebooks in VS Code

Notebooks are for exploring data and checking Findings by eye. They live in `notebooks/`.

**One-time kernel setup**

1. `uv sync` (ipykernel is already a dev dependency).
2. In VS Code: `Cmd/Ctrl+Shift+P` → **Python: Select Interpreter** → choose `.venv` (shown as `./.venv/bin/python`, or `.venv\Scripts\python.exe` on Windows).
3. Open any `.ipynb` → **Select Kernel** (top right) → **Python Environments** → the same `.venv`.

If `.venv` is not listed: reload the window (`Developer: Reload Window`), and check that you opened the repo root as the workspace folder, not a subfolder.

**First cell of every notebook**

```python
%load_ext autoreload
%autoreload 2
import timedetective
```

With autoreload on, edits to files in `src/` take effect without restarting the kernel.

**Notebook rules**

- Name them `NN_initials_topic.ipynb` (for example `01_pj_kansas_groundwater.ipynb`) so two people never edit the same file.
- A notebook may call skills and the engine. It may not be the only place a piece of logic lives: once something works, move it into `src/` with a test.
- Read data from `data/cache/`. To pull a new series, save it there with its source and retrieval date.
- Clear outputs before committing (`Clear All Outputs`), or run `uv run nbstripout --install` once to do it automatically.

## 4. Everyday loop

```bash
git pull && uv sync
make validate            # knowledge/ YAML against the schema
make test                # all fast tests
make calibrate           # after touching skills/ or the critic
make demo                # Streamlit demo
```

`make help` lists every task.

Work on short-lived branches, merge to `main` often, and keep `main` demo-able at all times.

## 5. Adding things

The recipes for adding a skill, a playbook or a data adapter, and the rules that must never be broken, are in [AGENTS.md](AGENTS.md). They apply to people as much as to AI agents. The fastest route is to copy the worked example: Mann-Kendall has a procedure YAML, a skill, a test and a playbook edge.

## 6. Who owns what this weekend

| Area | Folders |
| --- | --- |
| Statistical spine | `skills/`, `data/`, `tests/skills/`, `tests/calibration/` |
| Structure and story | `schema/`, `knowledge/`, `engine/`, `agent/`, `app/` |

Shared and frozen first: the Finding schema in `schema/core.yaml`. Talk before changing it.
