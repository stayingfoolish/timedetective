# Calibration: false-positive rates of the trend tests

Measured by `make calibrate` (`tests/calibration/test_false_positive_rate.py`): 500 trend-free
series per cell, white noise (phi = 0) or AR(1) noise, monthly cadence, nominal level 5%.
Target from AGENTS.md: at or below 5%. Numbers below are from the run on 2026-11-14.

| Procedure | phi=0, n=120 | phi=0, n=240 | phi=0.3, n=120 | phi=0.3, n=240 | phi=0.6, n=120 | phi=0.6, n=240 | Meets target |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `mann_kendall_prewhitened` | 3.6% | 6.6% | 3.6% | 6.8% | 4.0% | 6.8% | Yes, within Monte Carlo error |
| `mann_kendall` | 4.4% | 6.4% | 14.8% | 14.8% | 32.0% | 31.4% | No |
| `mann_kendall_hamed_rao` | 7.6% | 10.6% | 13.5% | 13.4% | 17.4% | 16.9% | No |
| `mann_kendall_tfpw` | 4.6% | 5.8% | 18.2% | 16.8% | 42.2% | 41.2% | No |
| `sens_slope` (interval excludes 0) | 4.4% | 6.4% | 14.8% | 14.8% | 32.0% | 31.4% | No |
| `ols_trend` | 4.4% | 6.4% | 13.6% | 15.2% | 32.0% | 32.4% | No |
| `ols_trend_hac` | 7.2% | 8.0% | 9.8% | 9.8% | 16.4% | 14.4% | No |

A separate 1,000-series run put `mann_kendall_prewhitened` between 4.5% and 6.6% for
phi up to 0.8 and n of 120 or 240, rising to 8.9% at phi = 0.8 with only 60 points.

## What this means

- Only `mann_kendall_prewhitened` can carry a "significant" claim under autocorrelation.
  The others are useful for the slope and its direction, not for the significance call.
- Trend-free prewhitening is worse than the uncorrected test on trend-free red noise.
- The Hamed-Rao correction and Newey-West errors help but stay two to three times over the target.
- `block_bootstrap_slope` was measured separately at 9% to 21% depending on block length; not calibrated either.
- Power of `mann_kendall_prewhitened`: 97% for a trend of 0.01 per step at phi = 0.6, n = 240.
  Prewhitening removes part of a real trend, so power will be lower for weaker trends.

## Update: prewhitened Mann-Kendall is not safe on records that wander

The table above uses AR(1) noise only. On annual series that contain a random walk, `mann_kendall_prewhitened`
fires on 21% to 26% of trend-free records, including a walk too small to see under ordinary noise. It also loses
most of its power when the trend is strong, because prewhitening removes the trend along with the autocorrelation.
It can no longer carry a "significant" claim on its own. See the end-to-end results below.

## End-to-end: the water storage check

`tests/calibration/test_storage_claim_policy.py` runs the whole path on synthetic records that copy the real GRACE
record's length and missing months: seasonal removal, annual means, the drift test, the detection floor, the
mission-gap caution and the critic. "Promoted" means the finding came out stronger than descriptive.
400 records per cell (200 for power); a cell passes at or below 7.5%.

| Trend-free record | Promoted | Drift test fired | Prewhitened Mann-Kendall fired | Mission-gap caution |
| --- | --- | --- | --- | --- |
| AR(1) noise, monthly phi 0 to 0.95 | 0.0% | 0.0% | 2.5% to 4.0% | 4.3% to 7.2% |
| AR(1), phi 0.98 | 0.0% | 0.0% | 9.0% | 5.0% |
| AR(1), phi 0.995 | 1.0% | 1.0% | 22.5% | 4.3% |
| Random walk (step 0.6) + noise 0.3 | 3.7% | 4.3% | 25.3% | 4.8% |
| Random walk (step 0.3) + noise 1.0 | 3.5% | 3.7% | 23.7% | 2.5% |
| Random walk (step 0.1) + noise 1.0 | 0.0% | 0.0% | 22.8% | 4.5% |
| Random walk (step 0.05) + noise 1.0 | 0.0% | 0.0% | 26.0% | 6.2% |
| Storage that only integrates rainfall | 0.0% | 0.0% | 20.7% | 5.2% |
| Walk with persistent steps, phi 0.5 | 3.5% | 3.7% | 27.3% | 7.2% |
| Walk with persistent steps, phi 0.8 | 4.5% | 4.8% | 30.7% | 9.0% |
| Walk with persistent steps, phi 0.9 | 5.2% | 6.2% | 35.7% | 8.0% |
| Walk with persistent steps, phi 0.95 | 4.3% | 8.7% | 44.5% | 5.8% |
| 6 cm offset at the mission change | 0.0% | 0.0% | 61.3% | 99.7% |

| Record with a real decline | Promoted | Drift test fired | Prewhitened Mann-Kendall fired |
| --- | --- | --- | --- |
| -1.0 cm a year, AR(1) phi 0.8 noise | 79% | 84% | 91% |
| -0.5 cm a year, AR(1) phi 0.5 noise | 70% | 74% | 89% |
| -3.8 cm a year on a random walk (step 1.3) | 84% | 91% | 93% |
| -1.4 cm a year on a random walk (step 0.9) | 37% | 42% | 57% |
| -1.4 cm a year, AR(1) phi 0.9 noise of sd 2 | 1.5% | 1.5% | 48% |

Reading it:

- The drift test with the critic's rules stays at or below 5.2% on every trend-free record tested.
- Its cost is the last row: a weak decline under large short-lived noise is almost never promoted. The finding
  still reports the slope and its range, as a description.
- The critic's limit on how alike successive yearly changes may be (lag-1 correlation at most 0.5) is what brings
  the smoothest walk from 8.7% down to 4.3%.
- The mission-gap caution fires on 2.5% to 9% of records with no offset, and on 99.7% of records with a 6 cm one.
- Slope range coverage (300 records each): 97% at monthly phi 0 and 0.5, 94% at 0.8, 91% at 0.9, 90% at 0.95.

Still not covered: long-memory noise, changes in variance, and any swing longer than the record. No test on 25
yearly values can rule those out, and the wording of a "significant" finding says so.

## Not done

- The weather playbooks have their own calibration record; their claims stay descriptive.
- Long-memory noise and seasonal residue are not covered for the individual procedures above.
- pymannkendall's `yue_wang_modification_test` rejected about 48% of white-noise series in a
  side check and was left out.
