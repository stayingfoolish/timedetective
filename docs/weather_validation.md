# Weather build validation — 2026-11-15 UTC

## Executed checks

| Check | Observed result |
| --- | --- |
| `make generate` | Generated both model files from LinkML; no hand-edited generated models |
| `make test` (final run) | **168 passed**, 8 slow tests deselected, 14.04 s |
| `make calibrate` | **2 passed, 6 expected failures**, 59.70 s; existing oversized-test expectations unchanged |
| `uv run python scripts/validate_knowledge.py --scope weather` | **0 problems**; 6 procedures, 1 playbook, 22 registry sources |
| `make validate` | **Fails on 34 pre-existing TODO procedure citations**, all outside the active weather graph |
| `git diff --check` | Passed |
| Offline Streamlit form | AppTest submitted the form and rendered a Finding without exceptions |
| Real-data adapter | All six variables exercised offline, 9,132 dates each, checksum verified |
| Independent arithmetic | Direct raw-JSON seasonal sums agree with the new pipeline; see [the values](examples/README.md) |

The first integration run exposed eight failures from treating the generated claim-strength
field as an Enum object when the generator uses string enum values. This was corrected in
the renderer/tests; the final full run above passed. No statistical acceptance threshold was
changed to obtain that result.

Known-answer and adversarial cases cover planted events and trends, constant/all-zero rain,
leap years, cross-year seasons, day-weighted temperatures, incomplete observations, duplicate
dates, invalid units/metadata, quality masking, fixed spatial support, checksum corruption,
uncited/cyclic/ambiguous graphs, product dependence, unsupported questions, and dated-history
overlap. Gaussian BIC differences are checked against Statsmodels rather than only against
the new implementation itself.

The additional seasonal/intermittent/persistent null tests check that the **claim cap cannot
be bypassed**. They do not measure weather-test power, establish confidence-interval coverage,
or validate significance: every current weather claim is deliberately descriptive.

## Readiness verdict

Ready for reproducible, evidence-traceable **descriptive investigations** of the supported
variables and supplied temporal/spatial support. Not ready to claim the full regional Horn
of Africa benchmark is resolved, to answer every weather question, or to certify significant,
robust or causal climate conclusions. Native-version regional data, common-support validation,
and full-pipeline inferential calibration are the next scientific gates, described in
[the playbook instructions](weather_playbook.md).

The existing environment was initially Python 3.9 with no uv. A temporary uv executable was
used to install the repository's unchanged lockfile into its Python 3.12 environment. No
project dependencies were added or changed. No commit or push was performed.
