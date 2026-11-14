# Building dataset-specific context

How to give TimeDetective what it needs to know about a particular dataset (GRACE water
storage, MODIS land surface temperature, SMAP soil moisture, a retail sales feed) without
putting any of that knowledge into the core.

**Status: none of this is built.** `packs/earth/` and `packs/retail/` are empty, `data/cache/`
holds no series, and `schema/core.yaml` has no class that describes a dataset. This file is
the build order and the list of what is still missing.

## The four pieces and where each lives

| Piece | What it holds | Location | Needs sign-off? |
| --- | --- | --- | --- |
| Dataset card | Facts about the dataset, as data | `knowledge/datasets/<pack>/<dataset>.yaml` | Yes: new `Dataset` class in the schema |
| Adapter | Code that fetches and shapes the data into a typed `Series` | `src/timedetective/packs/<pack>/adapters/` | Yes: the provider endpoint must be shown, not guessed |
| Domain edges | How the analysis differs for this domain | `knowledge/playbooks/*.yaml`, edges with `domain: earth` | Yes: `Playbook` class first |
| Cached series | The exact series the demo and the tests use | `data/cache/<pack>/` with a sidecar note | No |

Rule 3 in AGENTS.md decides the split: the core never imports a pack. Procedures and core
playbooks stay domain-free. Anything that knows what GRACE or NDVI is lives in a card, a
pack, or a domain-tagged edge.

## Build order

### Step 1. Agree the `Dataset` class

Draft for `schema/core.yaml` (then `make generate`):

```yaml
classes:
  Dataset:
    description: What the system knows about one data product, independent of any region.
    attributes:
      name: {identifier: true, required: true}      # equals the file name
      pack: {required: true}                        # earth, retail
      title: {required: true}
      plain_definition: {required: true}            # one or two sentences a student can read
      variable: {required: true}
      units: {required: true}
      provider: {}
      product_id: {}                                # the provider's short name and version
      cadence: {required: true}                     # native cadence, e.g. monthly, 8-day, daily
      analysis_cadence: {}                          # cadence the playbooks should regularize to
      record_start: {range: date, required: true}
      record_end: {range: date}                     # absent means ongoing
      seasonal_period: {range: integer}             # in steps of analysis_cadence; absent means none
      baseline_start: {range: date}                 # default climatology baseline
      baseline_end: {range: date}
      spatial_resolution: {}
      valid_min: {range: float}
      valid_max: {range: float}
      known_issues: {range: KnownIssue, multivalued: true, inlined_as_list: true}
      companions: {multivalued: true}               # datasets to check against (co-movement, independent record)
      source: {required: true}                      # key into knowledge/sources.yaml (user guide or paper)

  KnownIssue:
    description: A documented artifact that can look like a real change.
    attributes:
      kind: {range: IssueKind, required: true}      # gap, sensor_change, orbit_drift, reprocessing, short_record
      start: {range: date}
      end: {range: date}
      effect: {required: true}                      # what it does to the series
      handling: {required: true}                    # what the playbook should do about it
      source: {required: true}
```

Extend `scripts/validate_knowledge.py` to validate `knowledge/datasets/*/*.yaml` against
`Dataset`, with the same name-equals-file and source checks used for procedures.

### Step 2. Write one card per demo dataset

Fill every field from the product's user guide or algorithm document, and add that document
to `knowledge/sources.yaml`. Do not write a date or a unit from memory.

Example shape (values are placeholders to be confirmed against the user guide before commit):

```yaml
name: grace_tws
pack: earth
title: GRACE and GRACE-FO terrestrial water storage anomaly
plain_definition: >-
  How much more or less water (groundwater, soil moisture, snow, surface water combined)
  an area holds than its long-term average, measured from changes in Earth's gravity.
variable: terrestrial water storage anomaly
units: cm equivalent water thickness
cadence: monthly
analysis_cadence: monthly
record_start: TODO
seasonal_period: 12
known_issues:
  - kind: gap
    start: TODO        # end of the GRACE mission
    end: TODO          # first GRACE-FO month
    effect: About a year with no observations between the two missions.
    handling: Do not gap-fill across it; analyse with a gap-tolerant procedure or per mission.
    source: TODO
companions: [gpm_imerg_precipitation, gldas_soil_moisture]
source: TODO
```

Cards to write first: `grace_tws`, `modis_lst`, `smap_soil_moisture`, `gpm_imerg_precipitation`,
`modis_ndvi`, `noaa_cdo_station` (the independent record).

### Step 3. Cache the demo series

For each demo beat, save the series to `data/cache/earth/` as CSV with a sidecar
`<name>.meta.yaml` holding: dataset card name, region (name plus polygon or point), how it was
aggregated, retrieval date, the request or file it came from, and the checksum. Tests and the
demo read only from here. Do not overwrite a cached file; add a new one.

Needed: Kansas county groundwater and precipitation, Spokane neighbourhoods land surface
temperature (four series), Nebraska soil moisture, and one station record per site.

### Step 4. Define the typed `Series`, then write adapters

AGENTS.md requires adapters to return a typed `Series` with units, cadence, source and
retrieval date. That type does not exist yet; skills take a bare `pandas.Series` today.
Smallest workable option: keep `pandas.Series` and carry the metadata in `Series.attrs`,
with one helper in the core that reads and checks it.

Each adapter, in `src/timedetective/packs/earth/adapters/<dataset>.py`:

1. Reads the dataset card for units, cadence and valid range.
2. Fetches or loads the raw data (network only here, never in a skill).
3. Applies the product's quality flags and reports the share dropped.
4. Aggregates over the region (area-weighted) and reports the pixel count.
5. Returns the series with metadata attached. No regularizing or gap filling: that is the
   playbook's job, so it is recorded in the Finding's path.

One test per adapter, reading a small file from `data/cache/`.

### Step 5. Let playbooks read the card

The executor should seed the run's state from the card, so playbook edges can test card
properties exactly as they test procedure outputs:

- `seasonal_period` and `analysis_cadence` become parameters of `regularize`, `deseasonalize_*`, `anomaly`.
- `known_issues` of kind `gap` or `short_record` become properties an edge can refuse on before any test runs.
- A detected break (`pettitt`, `cusum`, `step_vs_trend`) is compared with `known_issues` dates;
  a match is reported as a likely artifact. This comparison is a new core procedure
  (`artifact_overlap`, category `robustness`), not pack code.

### Step 6. Add domain edges

Domain knowledge that changes the order of analysis goes in playbook edges tagged with the
domain and a source, for example:

- earth, groundwater: before reporting a decline, run `co_movement` against the precipitation companion.
- earth, soil moisture: with a record shorter than the detectability check requires, stop at descriptive.
- earth, land surface temperature: compare neighbourhoods on their paired difference (`slope_difference`), which removes shared weather.

Each needs a paper or a stated house rule. These edges are what the literature extractor is meant to produce.

### Step 7. Variable resolver

A lookup from a plain-language question to a dataset card and region, showing
`plain_definition` before any analysis. Deterministic matching on card titles and variables
can live in the core; anything that uses a model belongs in `agent/`.

## What is missing

**Blocking, needs a decision**

1. `Dataset` and `KnownIssue` classes (step 1), alongside the pending `Finding` and `Playbook` classes.
2. The typed `Series` and where its metadata lives (step 4).
3. Provider access: which endpoints or downloads, and which credentials, for AppEEARS, GRACE/GLDAS, GPM, SMAP and NOAA Climate Data Online.
4. The exact demo regions: which Kansas county, which four Spokane neighbourhoods (polygons), which Nebraska site.

**Blocking, needs work**

5. The executor and critic. Cards and domain edges have nothing to drive until they exist.
6. A "run once per region" step and a way to combine two results in one condition, both needed by the draft playbooks.
7. Region handling: polygon storage, area weighting, and what to do with partly covered pixels.
8. Unit and scale conversions (for example scaled integers and Kelvin in land surface temperature products), defined per card.

**Gaps in knowledge, not code**

9. A source for every card field and every known issue. None has been opened yet.
10. Sources for the 34 procedures still marked `TODO` and for every playbook edge.
11. Whether the chosen county has usable groundwater signal at GRACE's coarse resolution; the fallback is drought indicators.
12. Thresholds on edges (model-comparison margins, minimum record length) need a source or a house-rule label.

**Statistical gaps that dataset context exposes**

13. Only AR(1) noise is calibrated. Seasonal residue and long-memory noise, both common in Earth data, are not.
14. Gap-tolerant trend testing. Most trend skills refuse on missing values, and the GRACE gap is too long to fill; a Mann-Kendall path that accepts gaps, or per-mission analysis with a combined result, is needed.
15. Spatial dependence between regions. `fdr_correction` assumes independent or positively dependent tests; neighbouring areas need field significance.
16. Non-linear and count data: exceedance counts are counts, and the trend tests here assume continuous values.

**For the retail pack**

17. Cards for sales feeds need fields the Earth cards do not: calendar and promotion events, stockout flags, hierarchy level. Decide whether `Dataset` grows optional fields or the pack defines a subclass.
