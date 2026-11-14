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

## Not done

- No critic exists yet, so this measures individual procedures, not the end-to-end Finding.
- Only AR(1) noise is covered. Long-memory noise and seasonal residue are not.
- pymannkendall's `yue_wang_modification_test` rejected about 48% of white-noise series in a
  side check and was left out.
