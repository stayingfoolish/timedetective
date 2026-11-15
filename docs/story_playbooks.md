# Season check and water storage check: policy v1

This page is the house-rule source (`story_policy_v1`) cited by the two playbooks. It states what each
check does, which choices are project policy rather than taken from a paper, and what was changed and why.

Both checks stop at information. They describe a record, say how sure the description is, and say what
they cannot tell. They do not forecast, name causes, declare a crop failure or advise a decision. A question
that asks for those is still answered as far as the record goes, and the finding names what was left out.

## Season check (`knowledge/playbooks/season_check.yaml`)

Question: how unusual is this growing season for this place, compared with its own record?

| Step | What it does | Basis |
| --- | --- | --- |
| `season_audit` | Checks provenance, value range, the declared season months and the year. | House rule. The season is declared by the user for the place; it is never inferred from the data. |
| `season_series` | Monthly mean of the valid 16-day composites. Months with none stay missing. No smoothing, no filling. | House rule. Quality screening happens in the adapter (MOD13 reliability ranks 0 and 1, at least half the pixels kept); the MOD13 guide gives no formal rule. |
| `season_standing` | Ranks the season against the same months of every other season. For a season in progress it uses the months so far. | Comparing vegetation accumulated since the start of the season with the same period in earlier years follows the ASAP classification report (sections 5.1.2 and 5.2). ASAP uses z-scores below -1 on crop and rangeland masks; this check uses ranks on all land, so its bands are house rules. |
| `season_rainfall` | Ranks rainfall over the season months moved one month earlier and reports whether it agrees. | ASAP raises its warning level when a rainfall indicator and a vegetation indicator agree. The one-month lead is a declared default; correlations for leads 0 to 3 are reported. |

House rules:

- Bands by percentile of rank: at or below 10 "well below usual", at or below 25 "below usual", 25 to 75 "within the usual range", then "above" and "well above".
- Two indicators "agree" when both are at or below the 25th percentile, both at or above the 75th, or both in between.
- At least 10 comparable seasons; a missing month inside the target season is a refusal.
- If the seasonal record drifts (a step or trend model beats a flat one), the finding gives both the plain rank and the rank against a Theil-Sen line through the other seasons, and compares rainfall with the second. The drift is reported, not explained.
- Every finding is "descriptive". A rank is a description; no significance test applies.

Not done: no cropland mask, no crop calendar, no phenology, no yield. ASAP itself notes that vegetation anomalies can have causes other than drought and that automatic warnings need an analyst.

## Water storage check (`knowledge/playbooks/water_storage_check.yaml`)

Question: is the water stored in and under this region changing, and does the change follow rainfall?

| Step | What it does | Basis |
| --- | --- | --- |
| `storage_audit` | Checks provenance, whether the series is total water storage or groundwater, region size and record length. | Regions under 22 mascons are refused: the GSFC format description gives 22 mascons (about 300 km) as the approximate spatial resolution. |
| `storage_annual` | Removes the seasonal cycle with a two-harmonic fit that tolerates gaps, then averages by calendar year. | House rule. A year needs four months of data; thin years are listed in the finding. |
| `storage_trend` | Theil-Sen slope and range, the drift test, a second method, the detection floor, curvature and period sensitivity. | House rule; see "Which test decides" below. |
| `storage_handover` | Ranks the change across the 2017-2018 gap between missions against the same measurement at every other position in the record. | House rule. A change larger than 95% of the placebo positions attaches a caution and keeps the claim descriptive. |
| `storage_rainfall` | Regresses each year's change in storage on rainfall over the same two years. Reports the change in a spell of average rainfall. | Comparing a storage decline with rainfall over the same period follows Rodell et al. (2009). The regression is this project's simpler method, and its interval is descriptive. |

### Which test decides

Only the drift test can raise a claim to "significant": a t-test on the average yearly change, with the standard
error inflated for autocorrelation in the changes (never less than 0.25, the value produced by averaging a random
walk over each year). It keeps its false-alarm rate at or below 5% on short-lived noise and on records that wander
(see [calibration](calibration.md)). It has little power for a weak trend under large short-lived noise.

Mann-Kendall after prewhitening is run as a second method and reported. It is not accepted alone: on records that
contain a slow random walk it false-alarms 12% to 25% of the time.

The critic (`engine/critic.py`) then applies:

- significant: the drift test fired, 20 to 30 years, lag-1 correlation of yearly changes at most 0.5, the slope exceeds the detection floor, and no mission-gap caution.
- robust: all of that, plus the direction survives dropping up to four years from either end, the second method agrees, and an independent record agrees. No independent record is wired in yet, so no finding can reach "robust".

The slope range is the wider of the Theil-Sen interval and an autocorrelation-adjusted t interval. Measured coverage
is 97% with little persistence and about 90% at monthly persistence of 0.9 to 0.95, so it is called a range, not a
95% confidence interval.

### What a finding never says

- Why storage changed (pumping, irrigation, climate).
- A water-table depth, or how long a supply will last.
- "Groundwater", unless the series metadata records a documented subtraction of soil moisture, snow and surface water. The cached records are total water storage.

## Changes made after the first real records were loaded

These were changes to method, made because the first version was wrong on real data. Each was re-checked on
synthetic records before the real result was looked at again.

1. **Months per year, six to four.** The rule was written against an idealized 11-month gap. The real record has
   five solutions in 2017 and five in 2018, so six refused every real record. Synthetic records now copy the real
   pattern of missing months; false-alarm rate and slope recovery were re-measured with it.
2. **Significance test, prewhitened Mann-Kendall to the drift test.** The first version reported "no detectable
   trend" for north-west India, where storage fell about 85 cm. Prewhitening removes most of a strong trend along
   with the autocorrelation. Looking for a replacement showed a second problem: prewhitened Mann-Kendall false-alarms
   on slowly wandering records. The drift test fixes both. A consequence, not a goal: the High Plains decline, which
   the old test called significant (p = 0.027), is now reported as descriptive.
3. **Mission-gap check, Chow test to placebo ranking.** The Chow test at 2018 raised a caution on 8% of clean
   records and up to 77% of persistent ones. Ranking the change across the gap against the record's own changes
   raises it on about 5% whatever the persistence, and still catches a 6 cm offset.
4. **Wording.** "No detectable trend" is now used only when the slope range includes zero. A clear fitted slope that
   fails the test is reported as a slope, with the reason it is not called significant.
