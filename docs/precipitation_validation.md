# Precipitation implementation and validation record

## Outcome

Automatic point acquisition and analysis are implemented and tested on real NASA responses.
**Statistical certification is not complete.** The new stationary-bootstrap trend/period/
change tests exceed the 5% false-positive target for several dependence scenarios. They are
labelled `experimental_failed_dependence_calibration`; the unchanged critic keeps claims
descriptive. No threshold or null scenario was weakened to obtain a pass.

## Completed checks

- Full fast pytest suite: **203 passed, 8 slow tests deselected**. Includes existing weather tests plus new distillation, API-cache,
  real-data orchestration, missingness, source/unit/calendar checks, basic formulas,
  SPI/GEV conditional calculations, spell/timing, multiplicity and UI tests.
- `uv run python scripts/validate_knowledge.py --scope weather`: **15 procedures,
  3 playbooks, 32 sources, 0 problems**.
- `make validate`: **34 pre-existing TODO citation failures**, outside the executed graphs.
- `make calibrate`: **2 passed, 6 expected failures** in the legacy slow suite. This does
  not certify the new precipitation statistics.
- New audit: **500 replicates per scenario, 1,999 bootstrap draws, seed 77123**;
  seven scenarios, three component tests plus a three-test Holm family, and strong-signal
  power experiments. Exact binomial 95% intervals are retained in
  [the audit JSON](examples/precipitation_calibration_v2.json).

## Measured false-positive rates

The target remains 5%. `phi` is the latent Gaussian AR(1) coefficient, not necessarily
the Pearson lag-one correlation after transformation to precipitation amounts.

| Years | Null | Trend | Period contrast | Searched mean change | Three-test Holm family |
| --- | --- | --- | --- | --- | --- |
| 25 | Independent gamma | 3.6% | 3.8% | 1.6% | 0.6% |
| 25 | Gamma, phi=.6 | **11.2%** | **7.6%** | **8.0%** | **5.4%** |
| 45 | Independent gamma | 4.8% | 3.8% | 2.4% | 1.4% |
| 45 | Gamma, phi=.6 | **10.0%** | **9.4%** | **7.8%** | **5.6%** |
| 45 | Gamma, phi=.85 | **22.0%** | **16.4%** | **20.6%** | **11.6%** |
| 45 | Intermittent gamma, phi=.6 | **10.6%** | **8.0%** | **8.6%** | **5.2%** |
| 45 | Long-memory gamma copula | **14.8%** | **12.4%** | **12.8%** | **8.4%** |

Long memory uses fractional-integration weights d=.35 truncated at 500 lags, with a
1,000-step burn-in. This is a specified stress test, not all possible precipitation
dependence. Strong-signal trend power ranges from 46.6% to 83.6%; corresponding period
contrast power ranges 75.8%–99.6%. Higher power in oversized tests is not evidence of validity.
No observed-data conclusion is derived from these synthetic simulations.

The audit is component-level plus a single-product three-test family. It does not establish
confidence-interval coverage, daily-index inference calibration, spatial discovery control,
SPI severity accuracy, GEV tail/interval accuracy, or correctness of a real product.

Reproduce with a **new output path**:

```bash
uv run python scripts/calibrate_precipitation.py \
  --repetitions 500 --resamples 1999 --seed 77123 \
  --output downloads/my-calibration.json
```

The first audit finished its computations but encountered a NumPy Boolean serialization
error. That incomplete output is preserved under ignored downloads; it is not represented
as a valid result file. The writer was corrected to serialize before opening the destination,
and the exact same seeds, samples and thresholds were rerun to produce v2.

## Real API and offline replay

The CLI was exercised for **3°N, 42°E**, requested 1981–2024, MAM/OND seasons,
baseline 2000–2019 and event 2020–2022. The client fetched separate real daily UTC responses:

- `PRECTOTCORR`: 1981-01-01 through 2024-12-31.
- `IMERG_PRECTOT`: 1998-06-01 through 2024-12-31; earlier coverage explicitly unavailable.

Both raw responses and metadata are immutable snapshots under ignored `downloads/power`.
The historical-question replay is in `downloads/precipitation-live-v4/`: JSON bundle and Markdown
report. It ran with `--offline`, so no replacement data could be downloaded. Original v1/v2
outputs remain as historical run evidence; v2 predates the paired-missingness fix.

An additional real-data run, `downloads/precipitation-all-branches-v1/`, requests every
implemented analysis with baseline 1982–2011 and comparison 2012–2024. It uses the same
immutable responses and no network. MERRA-2 produced 12 calendar-month SPI fits, a
528-month SPI series including unavailable leading accumulation months, four conditional
GEV return levels, 2,157 spell records and 61 enclosed-window timing results. Timing
failures are retained, not filled. IMERG's inadequate baseline produces explicit SPI,
timing, baseline-comparison and GEV refusals while preserving supported descriptive work.
These outputs demonstrate execution, not statistical certification or physical truth.

The comparison retains both products and the whole 12-member testing family (2 products ×
2 seasons × 3 tests), including the four period-contrast refusals. The three-year event
cannot satisfy the declared ten-year-per-period statistical comparison precondition.
No significant, robust, causal or permanent-change claim was issued.

## Bugs caught during implementation

- Duplicate pytest module basenames prevented test collection; test modules received unique names.
- A paired DataFrame missingness reduction produced a Series instead of a Boolean; a
  unit test exposed it, and a real-data orchestration assertion now checks the completed
  daily-agreement result rather than accepting a generic executor refusal.
- The calibration writer's NumPy Boolean issue was fixed without changing statistics.
- The all-branches replay exposed a NumPy integer in SPI event duration serialization.
  Run boundaries now become Python integers at their producer; strict JSON regression
  checks cover successful SPI, timing and GEV values.
- A test expected product agreement without asking for that analysis; its question was
  corrected to request agreement explicitly. The application did not silently add the test.
- Whole-procedure refusals now retain all planned members in the testing family, and
  period inference refuses an out-of-coverage baseline rather than shortening it.

## What completion still requires

Replace or rigorously restrict the failed inference procedure, calibrate interval coverage
and power under the accepted null families, validate the SPI/GEV branches, and obtain the
explicit approval required by AGENTS.md before editing the critic. Approval alone cannot
turn failed statistical evidence into a significant claim. Native polygon acquisition and
general natural-language interpretation are separate remaining capabilities.
