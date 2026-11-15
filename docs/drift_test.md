# The drift test: where it comes from

`drift_test` asks one question: is the average step-to-step change different from zero, given how much the
changes vary? It is the only test in this project allowed to raise a finding to "significant"
([calibration](calibration.md), [policy](story_playbooks.md)).

## The test

For a series `x` with changes `d = x[t] - x[t-1]`, `m` of them:

1. `rho` = lag-1 correlation of `d`, but never less than 0.25 and never more than 0.8.
2. standard error = `sd(d) / sqrt(m) * sqrt((1 + rho) / (1 - rho))`
3. `t = mean(d) / standard error`, compared with Student's t on `m - 1` degrees of freedom.

Step 2 is the usual widening of a mean's standard error for first-order autocorrelation. The only unusual
part is the floor of 0.25 in step 1.

## Why 0.25

The yearly values the test is applied to are averages of monthly values. Averaging a random walk over
each period makes its period-to-period changes positively correlated, even though the walk's own steps
are independent. Cowles (1960) reports this effect and credits Holbrook Working with pointing it out and
proving it in an accompanying note. The Cowles paper was opened for this project; Working's note is
behind a paywall and was not, so the size of the effect is derived here and checked by simulation rather
than quoted.

Let the walk have independent steps `e` with variance `s²`, and let each period hold `m` points. The change
between two successive period averages weights the steps like a triangle: `1/m, 2/m, …, (m-1)/m` on the
later steps of the first period, then `1, (m-1)/m, …, 1/m` on the steps of the second. From that:

- variance of a change = `s² (2m² + 1) / (3m)`
- covariance of successive changes = `s² (m² - 1) / (6m)`
- lag-1 correlation = `(m² - 1) / (2 (2m² + 1))`

For monthly points in yearly averages, `m = 12`, this is 143/578 = 0.247. As `m` grows it tends to 1/4.
`tests/skills/trend/test_drift.py` checks the formula against simulated walks.

So a test that assumed independent yearly changes would be too confident on a wandering record. Using at
least 0.25 removes that. When the noise around a trend is short-lived instead, yearly changes are
negatively correlated, the floor overstates their variance, and the test errs on the cautious side.

## What it does not cover

- Changes that are themselves strongly persistent. The critic refuses to promote a finding when the lag-1
  correlation of yearly changes is above 0.5.
- A weak trend under large short-lived noise: the test will rarely fire (1.5% in one calibration cell).
- Swings longer than the record.

## Sources

- Opened: Cowles, A. (1960), "A Revision of Previous Conclusions Regarding Stock Price Behavior",
  Econometrica 28(4), 909-915; Cowles Foundation Paper 159.
- Not opened, cited by Cowles for the proof: Working, H. (1960), "Note on the Correlation of First
  Differences of Averages in a Random Chain", Econometrica 28(4), 916-918.
