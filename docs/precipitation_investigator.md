# Automatic precipitation investigator

## Readiness verdict

The **point-data workflow executes end to end**: deterministic distillation, automatic
NASA POWER calls, immutable caching, provenance/quality checks, cited YAML procedures,
multi-product testing-family correction, typed Findings and Markdown/JSON reports.

It is **not yet a validated universal statistical investigator**. The new dependent-data
bootstrap tests failed the repository's 5% false-positive target under persistent and
long-memory synthetic nulls. They remain explicitly experimental, and the critic remains
descriptive. SPI and stationary GEV outputs are conditional model calculations; their full
pipeline calibration/interval coverage is not established. Passing software tests does not
override these limitations. See [validation](precipitation_validation.md).

This extends, rather than silently changes, the older [weather workflow](weather_playbook.md).
No dependencies, Finding schema or claim-strength critic were changed in this extension.

## User inputs and distillation

Supply a point (latitude/longitude), complete-year start/end, baseline, comparison period,
seasons and question. The app shows all controls and has a **Preview distilled request**
button that does no network I/O. **Fetch and investigate precipitation** validates the
same contract before acquisition. All numerical defaults, selected procedures and targets
are retained in the report. A failed distillation never fetches data.

Distillation is a bounded keyword parser, **not an LLM semantic planner**. It recognizes
supported analysis families, SPI scales, named seasons, some return-period expressions
and conflicting year ranges. Explicit controls remain authoritative. It cannot geocode a
place name, determine arbitrary user intent, or certify that every clause was understood.
Inspect the preview. Unsupported causal, forecast, subdaily, cross-variable and selected
other requests are refused. Unknown questions need explicit analyses. Ambiguous extreme
trends need a statistical target rather than silently analyzing rainfall totals.

Supported targets for trend/period-change/changepoint tests:

- `seasonal_total`: complete annual or explicitly declared seasonal totals.
- `rx1day`, `rx5day`: annual daily maximum or within-calendar-year 5-day maximum.
- `wet_days`, `dry_spell`, `sdii`: annual wet-day count, within-year longest dry spell,
  and mean wet-day intensity. These targets currently require `annual` seasons.

The fixed wet-day threshold for these annual inferential targets is 1 mm/day; configurable
spell/agreement thresholds do not redefine these indices.

## CLI

Preview (no API call):

```bash
uv run python -m timedetective.packs.earth.precipitation \
  --question 'Compare MAM and OND precipitation trends, abrupt changes and product agreement' \
  --latitude 3 --longitude 42 --start 1981-01-01 --end 2024-12-31 \
  --baseline 2000 2019 --event 2020 2022 \
  --seasons '{"MAM":[3,4,5],"OND":[10,11,12]}' \
  --analyses summary trend period_change changepoint agreement --preview
```

Replace `--preview` with `--output downloads/my-investigation` to acquire and run.
The output directory must be new. Add `--offline` to prohibit network access and use only
already cached requests. API calls are outside the pure skills. The CLI returns recorded
refusals for scientific/data limitations; a written report is not itself proof of success.

The Python entry point is `investigate_question(question, cache_dir=..., **controls)`.
Use `run_request()` for an already distilled typed request. A `records` mapping is an
explicit network-free path for provenance-bearing daily point records. It verifies exact
requested timestamps and coordinates; arbitrary incomplete inputs are not silently sliced
into a successful full-record claim. Synthetic inputs are for separately labelled tests,
never substitutes for unavailable NASA observations.

## Acquisition contract

- Only the documented NASA POWER daily point endpoint is called, for `PRECTOTCORR`
  and `IMERG_PRECTOT`; no credential or question text is sent.
- MERRA-derived requests start no earlier than 1981-01-01; IMERG availability starts
  1998-06-01. Both are retained separately. Earlier IMERG coverage is recorded as unavailable,
  not generated, backfilled or silently replaced. The first partial IMERG year cannot
  support a full annual statistic. Statistical results retain actual years used.
- Completed historical calendar years only; current-year mixed/revised products are refused.
- Check response coordinates, requested date bounds, UTC, parameter, units, dates, fill
  values and checksums. Audit missing values without substituting zero.
- Three bounded attempts for transient failures; errors/refusals remain visible.
- Cache under ignored `downloads/power/<request-hash>/<snapshot>/`, **not** the committed
  demonstration cache. Reuse the original matching snapshot and verify its checksum.
  Corrupted entries are refused, not silently redownloaded. For an explicit refresh, use
  another cache directory; old evidence remains intact.
- POWER is a derivative export. It does not provide every native product-version or QC
  field. A point is a grid footprint, not a rain gauge or polygon average. Native MERRA
  and IMERG footprints differ. This implementation does not assert native-product certification.
- Comparisons use shared temporal support. Full-record trend fits can have different start
  years between products; those slopes are not automatically comparable estimates of one period.

## Procedures and scientific boundaries

All analysis ordering is in [precipitation.yaml](../knowledge/playbooks/precipitation.yaml)
and [precipitation_family.yaml](../knowledge/playbooks/precipitation_family.yaml).

| Procedure | Calculation | Preconditions / interpretation |
| --- | --- | --- |
| Totals | Complete monthly and annual sums, null for incomplete support | No climatological baseline needed for the arithmetic |
| Seasonal baseline | Existing anomalies, empirical ranks, baseline sensitivity and exploratory BIC models | Default 15 complete baseline years; no empirical rank is a p-value |
| Trend | OLS slope, Sen slope, stationary-null bootstrap p, residual-bootstrap basic interval | >=20 nonconstant complete seasonal years; experimental, failed general dependence calibration |
| Period contrast | Prespecified event-minus-baseline mean, stationary-null bootstrap | >=10 complete years in each disjoint period; no unsupported difference CI emitted |
| Mean-change search | Maximum absolute standardized mean contrast over admissible boundaries, bootstrap repeats full search | >=8 years each side; a smooth trend can also trigger it; no precise breakpoint CI or causal date |
| Multiplicity | Holm across declared methods, seasons and products | Refused members retained as p=1; correction cannot repair invalid local p-values |
| Daily indices/spells | Rx1day, within-year Rx5day/CDD, wet-day counts/total/SDII, R10/R20; cross-year run catalogue | Missing days break spells and mark censoring; not full cross-year ETCCDI annual assignment |
| SPI | Rolling accumulation, per-ending-month positive gamma MLE, zero mass q, normal inverse; negative runs reaching -1 | >=30 baseline accumulations per calendar month, >=20 nonconstant positives; fit screen; no claim of impact or exact tail probability |
| Return levels | SciPy stationary GEV MLE on complete annual Rx1day maxima, parametric bootstrap intervals, refitted KS screen | >=30 complete consecutive years, 1<T<=2n; conditional on stationary independent annual maxima, not IDF or floods |
| Timing | Minimum/maximum cumulative rainfall anomaly in explicit broad windows | >=15 complete baseline years, complete >=30-day windows; boundary solutions refused; adapted stage 2 of Dunning, not automatic harmonic season discovery or planting advice |
| Product agreement | Daily signed difference, RMSE, MAE, correlation, wet-day contingency; seasonal anomaly signs | >=365 complete paired days; neither product is truth; no independence claim |

### Disclosed house rules and assumptions

1. Statistical targets, years, seasons and family are declared before examining results.
   Season subsets are not selected because they are significant. Iterating questions still
   introduces analyst selection not controlled by the within-run correction.
2. Bootstrap mean block lengths are `2`, rounded `n^(1/3)`, and twice that value capped at
   `floor(n/4)`, deduplicated. Retain all results and use the largest p-value, not the best
   one. This sensitivity rule **did not** eliminate dependence-driven size distortion.
3. Use explicit seeds and `(1 + exceedances)/(B+1)`, never a zero Monte Carlo p-value.
   Default B=1999; fitted-distribution bootstrap B=199. These defaults and p resolution
   are recorded. The latter is modest and not certification of precise tail uncertainty.
4. Trend intervals resample detrended residuals. Trend/mean-change null tests resample the
   centered original series. Each is conditional on its respective short-memory/stationary
   assumptions. They are not exact randomization tests for arbitrary precipitation.
5. Finite-sample minimums are safeguards, not guarantees derived from a universal theorem.
   Non-rejection cannot establish no change, equivalence, homogeneity or stationarity.
6. SPI uses `q+(1-q)*GammaCDF(x)` and normal PPF, with probabilities clipped to
   `[1e-8,1-1e-8]` and clipping counts reported. Zero observations use the upper atom q;
   interpretation in arid months is limited. Incomplete rolling windows stay missing.
   Fit-screen p<.01 refuses that calendar month, retaining all other failures/results.
   Screening is diagnostic, not a valid post-selection guarantee. Overlapping SPI values
   are dependent. Our gamma MLE is **not** Copernicus's L-moment implementation.
7. GEV fits use SciPy shape c (also report conventional xi=-c); refit every bootstrap draw.
   Any failed fit refuses the calculation. KS screening uses refitted bootstrap statistics,
   not the invalid ordinary fitted-distribution KS p-value. The model's stationarity and
   independence remain assumptions, even if diagnostics fail to reject.
8. Timing is a clearly labelled adaptation: broad windows are supplied, not inferred with
   the paper's harmonic stage. Per-year onset is the day after the cumulative minimum;
   cessation is the following maximum. Ties use first occurrence. Do not infer a change
   in timing from these descriptive dates without another validated test.
9. Core executor now propagates batched `subprocedure_refusals` into Finding refusals;
   optional failures never vanish just because other procedures succeeded. This generic
   engine change is needed for calendar-month/season-specific failures, not domain routing.
10. Runtime versions, source-code hashes, input hashes, resolved parameters, citation
    snapshots and graph hashes are retained. Deterministic reports use only run evidence.

## Literature-to-implementation map

- [Politis & Romano (1994)](https://doi.org/10.1080/01621459.1994.10476870) and
  [arch documentation](https://arch.readthedocs.io/en/latest/bootstrap/generated/arch.bootstrap.StationaryBootstrap.html):
  stationary-bootstrap index construction. Composite precipitation tests and block choices
  are our policy, **not** a claim of proven finite-sample validity from that paper.
- [Dunning, Black & Allan (2016)](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2016JD025428):
  selected method sections 2.2.1–2.2.3 reviewed; adapted stage-2 cumulative anomaly timing.
- [Zhang et al. (2011)](https://www.geos.ed.ac.uk/~ghegerl/assets/WIRES_index.pdf):
  daily precipitation index definitions and aggregation limitations.
- [IDMP SPI guidance](https://www.droughtmanagement.info/standardized-precipitation-index-spi/),
  [Copernicus SPI factsheet](https://drought.emergency.copernicus.eu/data/factsheets/factsheet_spi.pdf),
  [SciPy gamma](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.gamma.html):
  index definition, reference length, drought episodes and actual fitted distribution.
- [SciPy GEV](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.genextreme.html)
  and [refitted goodness-of-fit](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.goodness_of_fit.html):
  library implementation and fitting-uncertainty handling. This is an implementation-doc
  basis, not a claim to have reviewed an exhaustive extreme-value theory literature.
- [Statsmodels multiplicity](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html)
  and [Wilks (2016)](https://read.nxtbook.com/ametsoc/bams/december2016/essay_thestipplingshows.html):
  family correction and the need to retain all tests.

See the existing [literature audit](weather_literature.md) and the machine-readable
[source registry](../knowledge/sources.yaml) for access levels. The 34 pre-existing TODO
sources are still unresolved; none is used by these precipitation playbooks.

## Remaining completion gates

- Replace or validate the failed trend/change inference under the supported dependence
  classes, without weakening the 5% criterion. Measure interval coverage and power too.
- Validate SPI distributions/zero handling and GEV interval coverage on realistic regimes;
  independent gauge/reference comparisons are still needed for observational accuracy.
- Explicit approval is still required by AGENTS.md before editing the critic; permission
  alone would not justify lifting the statistical gate.
- Native gridded/polygon acquisition, arbitrary semantic planning, hourly IDF/POT models,
  nonstationary extreme-value models, equivalence tests, and causal/forecast workflows
  remain outside implemented coverage. Unsupported evidence must be refused.

The original broad scientific-completion goal is therefore **not complete**, even though
the automatic point-data workflow now runs end to end.
