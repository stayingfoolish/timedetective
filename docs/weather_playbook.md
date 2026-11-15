# Weather evidence playbook v1

For the newer automatic precipitation-only acquisition and expanded procedures, see
[precipitation investigator](precipitation_investigator.md). This page documents the
unchanged original offline weather route, not the new route's capability list.

## Status and scope

Implemented as a bounded, offline, descriptive evidence workflow—not a universal weather
oracle. It loads real cached NASA values and user-supplied, provenance-bearing CSVs.
The executor follows [weather.yaml](../knowledge/playbooks/weather.yaml); only the critic
assigns claim strength. No LLM or network call occurs during analysis.

This implements the additive Finding/Playbook/Dataset proposal requested for the weather
build. It does not promote the four older draft playbooks into production. The first Finding
schema version is `0.1`. Generation still starts from [core.yaml](../schema/core.yaml);
`make generate` produces both the reference and importable runtime models. Do not hand-edit them.

| Question | Implemented evidence | Boundary |
| --- | --- | --- |
| Was a specified season unusually dry/wet? | Totals, anomalies, empirical ranks, low-quantile counts | Not SPI, return period, crop impact, or drought severity certification |
| Event, step, or longer trend? | Flat/linear/step/step+trend/specified-episode comparisons, Sen slope, HAC interval, endpoint sensitivity | Exploratory models; neither a permanent change nor its absence is proved |
| Did rainfall recover? | Every complete seasonal year is retained, including years after the event | Recovery and a longer-term trend can coexist |
| Do precipitation products agree? | Same baseline/event, anomaly signs, low-quantile counts, grid resolutions and lineage | Common coordinates do not mean common footprints or independent errors |
| What happened to temperature, wind, humidity, pressure? | Complete-calendar monthly and seasonal means, anomalies and exploratory slopes | Not gusts, heatwave indices, sea-level pressure, or a forecast |
| Were daily rain extremes different? | Annual Rx1day, within-year Rx5day, wet-day total/count/intensity, within-year dry spell | Not hourly extremes, floods, design storms, or full cross-year ETCCDI spells |
| Discover changes without naming a region | `discover()` inspects all provided series and retains all seasonal years | No global data retrieval, automated event-window search, or inferential spatial discovery |
| Did a sensor change explain a boundary? | Cited metadata overlap screen | A match is not attribution; missing metadata is a recorded refusal |
| Why did it happen? What happens next? | Explicit unsupported-intent refusal | Requires a separate validated attribution/forecast workflow |

The prose question is preserved, not interpreted as a complete executable specification.
Declare dates, seasons, variables and support in the controls/API. A conservative keyword
guard refuses common unsupported causal/forecast/SPI requests; it is not a general-language
semantic verifier. The UI displays the actual analysis configuration for inspection.

## Run the real-data example

```bash
uv sync --frozen
uv run python scripts/validate_knowledge.py --scope weather
uv run python -m timedetective.packs.earth.run \
  --data data/cache/earth/power_3N_42E_2000_2024_20261115.json \
  --parameter PRECTOTCORR --companion IMERG_PRECTOT \
  --question 'Compare the 2020–2022 seasons and assess longer-term change at this point' \
  --seasons '{"MAM":[3,4,5],"OND":[10,11,12]}' \
  --baseline 2000 2019 --event 2020 2022 \
  --output weather_finding.json
make demo
```

Output paths must be new: Findings and caches are not overwritten. A committed example is
in [examples/](examples/). Its source is 9,132 daily records per variable at **3°N, 42°E**,
2000–2024. This is **not** the previously proposed 3°S–12°N, 38°E–49°E area mean.
The original response and sidecar are in [data/cache/earth/](../data/cache/earth/).
The download date is UTC; local Central time was November 14.

The live NASA documentation now exposes `IMERG_PRECTOT` through POWER daily UTC.
The observed response reports `mm/day`; the documentation table describes daily sums as
`mm`. Integration over one day is the same numeric amount. The adapter checks these exact
documented/observed alternatives; it does not infer native IMERG V07 status from the POWER
API version. Native retrieval quality flags are not present in this export.

## Enforced rules (weather_policy_v1)

These are transparent **house rules**, not thresholds claimed to come from a paper.

1. Require source, retrieval date, product/version, units, cadence, variable, quality statement,
   checksum, time standard and spatial support. Validate file checksums before analysis.
2. Never replace missing rain with zero. Reject duplicate/irregular dates; explicit missing
   observations remain NaN. Require every daily value for a monthly statistic, and every
   monthly value for a seasonal statistic. Partial calendar years cannot support annual extremes.
3. Precipitation is an accumulation, other supported variables are means. Convert monthly
   mean daily precipitation rate using actual calendar month length, including leap days.
   Seasonal weather means are day-weighted. Kelvin converts by subtracting 273.15.
4. Seasons must be explicit, contiguous and ordered. Cross-year seasons use their ending
   year. Defaults are annual, not an assumption that all regions have MAM/OND rainy seasons.
   Month-by-month analysis is available to expose heterogeneity within MAM/OND.
5. Use an entirely observed, earlier, non-overlapping baseline. Default 2000–2019 is an
   analysis reference, **not a WMO 30-year climate normal**. Default minimum is 15 complete
   baseline years. API overrides cannot reduce it below 10. Do not choose another baseline
   silently after missing observations or an inconvenient answer.
6. The low-season threshold is the baseline 20th percentile, with strict `<`. Report the
   actual threshold. Do not relabel this cutoff “severe drought,” SPI, or a 1-in-5-year event.
   All-zero rainfall yields null percent anomalies, not infinity.
7. Baseline sensitivity drops five years from either end where at least ten remain.
   Endpoint sensitivity trims three years from the beginning/end/both. These ranges describe
   sensitivity, **not confidence intervals**. Reference 10th–90th percentiles describe
   historical variability, not uncertainty in the mean.
8. Candidate models need at least 15 consecutive seasonal years; step candidates need five
   years on each side. BIC counts a searched step position as a parameter. A specified event
   window is fixed, not a data-selected breakpoint. IID Gaussian model ranks are exploratory
   for skewed, persistent precipitation. HAC uses two lags and a nominal 95% interval;
   it has **not** been calibrated here for inferential weather claims. No weather p-value is
   silently promoted to a decision. The fitted residual lag-1 value is retained.
9. Compare products only for the same variable, requested spatial support, units and time
   standard. Report different native footprints and shared inputs. Even matching products
   do not establish independent evidence. A point comparison cannot be generalized to a region.
10. Screen selected step-model boundaries against cited dated observing history using a
    ±1-year tolerance (seasonal-year resolution). Record lack of history as a refusal. This
    does not homogenize data or establish the cause of a break.
11. Graphs must be acyclic, reachable, fully cited and have exhaustive, unambiguous `ok` /
    `refused` or `always` routing. Every path ends in a claim request or refusal. Failed
    optional extremes/comparison/history checks remain in the Finding; no silent fallback.
12. The critic currently caps all weather results at descriptive. Calibration of the old
    prewhitened MK function does not validate this new seasonal/discovery pipeline. No causal,
    permanent-change, forecast, “no change,” or superiority-over-ChatGPT conclusion is implied.
13. Keep the complete search family in blind discovery. Empirical ranks are not p-values;
    do not run FDR on them. Spatial inference needs validated local tests, dependence-aware
    field control and held-out confirmation; these are not implemented.
14. The report is a deterministic rendering of Finding fields. Steps contain resolved
    parameters, results, method and edge sources, reference snapshots and playbook/source
    fingerprints. `_references` and `_run_contract` are provenance metadata, not skill arguments.

## Bring regional or other weather data

Use `--format csv --data primary.csv --companion-data second.csv` with a sidecar of the
same stem ending `.meta.yaml`. For a single series use `date,value` columns. For a region use
`date,cell_id,value,weight_km2`; weights are precomputed polygon-clipped cell areas, constant
over time, positive and finite. The adapter requires every cell, never renormalizes to a
changing observed footprint, and records pixel count, total area and incomplete dates.
Generate polygon intersections upstream using the native product grid; simple unweighted
pixel means are not an acceptable regional precipitation substitute.

Sidecar required fields: `name`, `sha256`, `source`, `retrieved` (quoted ISO date), `product`,
`version`, `variable`, `units`, `cadence`, `time_standard`, `spatial_support`, `quality`.
Optional: `missing_values`, `lineage`, `known_issues`, `spatial_resolution`. If `quality_flag`
exists, supply `accepted_quality_flags`. For a gridded CSV supply `weights_source` and
`spatial_support: {kind: polygon, ...}` with the actual polygon/identifier and provenance.
Accepted variables: precipitation, temperature, wind_speed, relative_humidity, surface_pressure.
Cadence: daily or month-start monthly. Precipitation units: mm/day, daily mm, monthly mm/month.
Native NetCDF/HDF adapters and coordinate reprojection are **not** implemented.

## Benchmark and readiness gate

The other chats asked for a fair comparison using the same data, coordinates, metadata and
tools, without web-derived event answers. Keep those conditions. Hide the geographic name,
not coordinates, units or provenance. Score arithmetic, complete seasons, missingness,
uncertainty labels, product disagreement, sensor history, and unsupported assertions.

The real point result is deliberately not hard-coded as the expected drought answer. It
contains opposite anomaly signs between the two products. It proves the pipeline executes
on real inputs and exposes disagreement; it does not validate the whole regional drought case.

Before calling the original regional benchmark complete:

- Acquire version-identified, quality-filtered native products over the declared region.
- Aggregate both to the same land/polygon footprint and UTC temporal support.
- Review observing history and add a longer-record companion or genuinely independent gauges.
- Calibrate weather inference under seasonal intermittency, persistence, long memory and
  realistic missingness; measure false positives **and power**. The current claim-cap tests
  are policy regression tests, not inferential calibration.
- Add spatial selection/multiplicity control before reporting discovered hotspots as significant.
- Do not claim to answer every weather question: add a cited, tested procedure or return
  an explicit limitation for unsupported requests.

## Checks

`make test`, `make calibrate`, `make validate`, and the scoped validator above were run for
this build. Full validation still exposes **34 pre-existing TODO citations**, none used by
the weather graph. Do not suppress that failure. The calibration suite's six expected
failures are known oversized tests; their thresholds were not loosened.
