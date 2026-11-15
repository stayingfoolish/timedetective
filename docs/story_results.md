# The two checks on real NASA records

Branch `real-data-stories`. Everything here was produced by `timedetective.packs.earth.stories` from the files in
`data/cache/earth/stories/`, and is pinned by `tests/engine/test_stories_real_data.py`. Method and house rules are in
[story_playbooks.md](story_playbooks.md); false-alarm rates are in [calibration.md](calibration.md).

## What was fetched (15 November 2026)

| File | Size | SHA-256 (start) | Source |
| --- | --- | --- | --- |
| `gsfc_mascons_nw_india.csv`, `gsfc_mascons_high_plains.csv` | 330, 341 KB | `4ca1cff809c8`, `178198bd3408` | Subsets of the NASA GSFC GRACE/GRACE-FO mascon file `GSFC.glb_.200204_202606_RL06v2.0_OBP-ICE6GD.h5` (174 MB, SHA-256 `2078d0ac3bce…`, not committed), cut by `scripts/extract_gsfc_mascons.py` |
| `modis_MOD13Q1_3.0061N_34.1125E_5km_…json.gz`, `…_2km_…json.gz` | 2.0 MB, 379 KB | `4709183a375c`, `785f880e0182` | ORNL DAAC subset service, MOD13Q1 NDVI and pixel reliability, 614 composites, 124 responses each |
| `power_3.006N_34.112E_2000_2025_…json` | 289 KB | `7e78a3a34dee` | NASA POWER daily point, IMERG and MERRA-2 corrected rainfall |
| `power_monthly_PRECTOTCORR_SUM_{nw_india,high_plains}_…json` | 440, 523 KB | `4f2a7b6465f5`, `954378dddc60` | NASA POWER monthly regional rainfall totals |
| `power_monthly_GWETPROF_{nw_india,high_plains}_…json` | 415, 489 KB | `aadab26df251`, `ba252b33098d` | NASA POWER monthly regional profile soil wetness |

Each file has a `.meta.yaml` beside it with the full request address, checksum and retrieval date.

How they were fetched: the cloud workspace cannot reach NASA servers, so the requests were made in a desktop browser
session. Each response's SHA-256 was computed in the browser before saving and re-checked after transfer. No login was
needed for any of these.

Not fetched: GLDAS (soil moisture, snow and surface water to subtract from total storage). It needs a NASA Earthdata
login. Until it is added, the storage findings are about **total water storage**, and say so.

## Water storage

Regions are the land mascons whose centres fall inside a declared box, taken whole. Rainfall is averaged over the box.

| | North-west India | US High Plains |
| --- | --- | --- |
| Box | 27-32°N, 73-78°E | 34-40°N, 104-99°W |
| Mascons, area | 26, about 322,000 km² | 27, about 334,000 km² |
| Record | April 2002 to June 2026, 258 of 291 months | same |
| Theil-Sen slope, cm of water a year | -3.8 (range -4.2 to -3.3) | -1.4 (range -1.8 to -0.9) |
| Drift test (decides significance) | fired, p = 0.018 | did not fire, p = 0.12 |
| Prewhitened Mann-Kendall (second method) | did not fire, p = 0.11 | fired, p = 0.027 |
| Direction stable when years are dropped | yes | yes |
| Change across the mission gap | -8.6 cm; 18% of placebo positions are as large; no caution | -1.2 cm; 74% are as large; no caution |
| Change in a spell of average rainfall, cm a year | -3.6 (range -5.7 to -1.5) | -1.4 (range -2.6 to -0.1) |
| Storage response to 100 mm more yearly rain | 1.1 cm (range -0.8 to 2.9), not clear | 2.8 cm (range 1.1 to 4.6) |
| Rainfall trend over 2000-2025 | increasing | none detected |
| Provider leakage trend uncertainty, cm a year | 1.1 | 0.6 |
| **Claim strength** | **significant** | **descriptive** |

North-west India, as the check words it:

> Total water storage in this region fell by about 3.8 cm of water per year between 2002 and 2026 (range 3.3 to 4.2),
> about 90 cm in total. In a spell of average rainfall, storage still fell by about 3.6 cm a year (range 1.5 to 5.7),
> so rainfall alone does not account for the decline. Rainfall itself has been increasing over the period.

High Plains:

> On a straight-line fit, total water storage in this region fell by about 1.4 cm of water per year between 2002 and
> 2026 (range 0.9 to 1.8). Year-to-year changes vary too much for that to pass this project's significance test: a
> record that simply wanders could look like this. […] Wetter spells do help: each extra 100 mm of yearly rain goes
> with about 2.8 cm more storage.

Plausibility check against the literature: over August 2002 to October 2008 the north-west India series falls 4.7 cm a
year. Rodell et al. (2009) report 4.0 ± 1.0 cm a year of groundwater loss for that period over Rajasthan, Punjab and
Haryana. The quantities differ (total storage against groundwater; a box against three states), so this shows the
series is in the right range, not that the method is validated.

Why neither can be "robust": the two trend methods disagree in both regions, and no independent record (observation
wells) is wired in.

## Season check, area around Kotido, Karamoja, Uganda

Declared growing season: April to September. Vegetation: mean NDVI of good and marginal pixels in a 10 km box
(3.0061°N, 34.1125°E); 3 of 614 composites failed the quality rule; no month is missing. Rainfall: NASA POWER point
record, March to August totals (one-month lead).

| Season | Greenness rank of 27 (1 = lowest) | Against the record's drift | Rainfall rank of 26, IMERG | Rainfall rank of 26, MERRA-2 | Two indicators |
| --- | --- | --- | --- | --- | --- |
| 2009 | 1, well below usual | 1, well below usual | 1, well below usual | 1, well below usual | agree: both low |
| 2021 | 19, usual | 14, usual | 3, well below usual | 9, usual | differ (IMERG); agree (MERRA-2) |
| 2022 | 22, above usual | 17, usual | 5, below usual | 16, usual | differ (IMERG); agree (MERRA-2) |
| 2025 | 27, well above usual | 27, well above usual | 16, usual | 23, above usual | differ (IMERG); agree (MERRA-2) |
| 2026 | 11, usual | 1, well below usual | not available | not available | vegetation only |

Things the record shows that the finding states:

- 2009 stands out in both indicators, with either rainfall product and with a 4 km box instead of 10 km (rank 2).
- Greenness has drifted upward (about 0.05 NDVI a decade). The check reports the plain rank and the rank against that
  drift. For 2026 they differ sharply: ordinary against the whole record, lowest against the drift.
- Season rainfall and greenness move together across years (Spearman 0.50 at the one-month lead).
- The two rainfall products disagree about 2021 and 2022. The check reports whichever is supplied; it does not pick.
- 2026 rainfall is refused: the rainfall adapter accepts completed years only.

Cautions that are not yet in the dataset card because no source has been opened for them: Terra MODIS is near the
end of its life and its orbit has drifted, which can affect recent values. The 2026 reading should be checked against
VIIRS (`VNP13A1`, served by the same service) before it is shown as more than a description.

## Reproduce

```bash
uv run pytest tests/engine/test_stories_real_data.py      # the pinned results
make demo                                                  # both checks are at the bottom of the page
uv run python scripts/validate_knowledge.py --scope stories
```
