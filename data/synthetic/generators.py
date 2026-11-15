"""Seeded synthetic series with known answers, for skill tests and calibration.

Every generator takes an explicit seed and returns a pandas Series (monthly
DatetimeIndex unless stated). Tests load this module through tests/conftest.py.
"""

import numpy as np
import pandas as pd


def _index(n: int, freq: str = "MS", start: str = "2000-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq=freq)


def white_noise(n: int = 240, sigma: float = 1.0, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0, sigma, n), index=_index(n), name="white_noise")


def ar1(n: int = 240, phi: float = 0.6, sigma: float = 1.0, seed: int = 0) -> pd.Series:
    """Stationary AR(1) noise with innovation SD `sigma`; no trend."""
    rng = np.random.default_rng(seed)
    e = rng.normal(0, sigma, n)
    x = np.empty(n)
    x[0] = e[0] / np.sqrt(1 - phi**2)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + e[t]
    return pd.Series(x, index=_index(n), name="ar1")


def random_walk(n: int = 240, sigma: float = 1.0, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(np.cumsum(rng.normal(0, sigma, n)), index=_index(n), name="random_walk")


def linear_trend(
    n: int = 240, slope_per_step: float = 0.02, sigma: float = 1.0, phi: float = 0.0, seed: int = 0
) -> pd.Series:
    """Linear trend plus white (phi=0) or AR(1) noise."""
    noise = ar1(n, phi, sigma, seed) if phi else white_noise(n, sigma, seed)
    return (noise + slope_per_step * np.arange(n)).rename("linear_trend")


def seasonal(
    n: int = 240, period: int = 12, amplitude: float = 3.0, slope_per_step: float = 0.0,
    sigma: float = 1.0, seed: int = 0,
) -> pd.Series:
    """Sinusoidal season plus optional trend plus white noise."""
    t = np.arange(n)
    x = amplitude * np.sin(2 * np.pi * t / period) + slope_per_step * t
    return (white_noise(n, sigma, seed) + x).rename("seasonal")


def step_change(n: int = 240, at: int = 120, size: float = 3.0, sigma: float = 1.0, seed: int = 0) -> pd.Series:
    """Flat, then a level shift of `size` from position `at` on."""
    x = white_noise(n, sigma, seed)
    x.iloc[at:] += size
    return x.rename("step_change")


def slope_change(
    n: int = 240, at: int = 120, slope_before: float = 0.0, slope_after: float = 0.05,
    sigma: float = 1.0, seed: int = 0,
) -> pd.Series:
    """Continuous piecewise-linear mean with a slope change at `at`."""
    t = np.arange(n)
    mean = slope_before * t + (slope_after - slope_before) * np.clip(t - at, 0, None)
    return (white_noise(n, sigma, seed) + mean).rename("slope_change")


def coupled_pair(
    n: int = 240, lag: int = 3, beta: float = 0.8, sigma: float = 0.5, seed: int = 0
) -> tuple[pd.Series, pd.Series]:
    """x is AR(1); y follows x with a delay of `lag` steps (x leads y)."""
    x = ar1(n + lag, 0.5, 1.0, seed)
    rng = np.random.default_rng(seed + 1)
    y = beta * x.to_numpy()[:n] + rng.normal(0, sigma, n)
    idx = _index(n)
    return (
        pd.Series(x.to_numpy()[lag:], index=idx, name="x"),
        pd.Series(y, index=idx, name="y"),
    )


def decoupling_pair(
    n: int = 240, at: int = 120, beta: float = 1.0, drift_after: float = -0.05,
    sigma: float = 0.5, seed: int = 0,
) -> tuple[pd.Series, pd.Series]:
    """y tracks x until `at`, then drifts away at `drift_after` per step."""
    x = ar1(n, 0.5, 1.0, seed)
    rng = np.random.default_rng(seed + 1)
    drift = drift_after * np.clip(np.arange(n) - at, 0, None)
    y = beta * x.to_numpy() + drift + rng.normal(0, sigma, n)
    return x.rename("x"), pd.Series(y, index=x.index, name="y")


def cointegrated_pair(n: int = 300, beta: float = 2.0, sigma: float = 0.5, seed: int = 0) -> tuple[pd.Series, pd.Series]:
    """Two random walks sharing one stochastic trend."""
    x = random_walk(n, 1.0, seed)
    rng = np.random.default_rng(seed + 1)
    y = beta * x.to_numpy() + rng.normal(0, sigma, n)
    return x.rename("x"), pd.Series(y, index=x.index, name="y")


def with_gaps(x: pd.Series, positions: list[int]) -> pd.Series:
    """Copy of `x` with NaN at the given integer positions."""
    y = x.copy()
    y.iloc[positions] = np.nan
    return y


def seasonal_weather(seed: int = 0, episode: bool = False, slope: float = 0.0) -> pd.Series:
    """Labelled synthetic monthly rainfall for known-answer tests, never real evidence."""
    idx = pd.date_range("2000-01-01", "2024-12-01", freq="MS")
    rng = np.random.default_rng(seed)
    y = 50 + 20 * np.sin(2 * np.pi * (idx.month.to_numpy() - 1) / 12)
    y = y + slope * (idx.year.to_numpy() - 2000) + rng.uniform(-5, 5, len(idx))
    if episode:
        y[(idx.year >= 2020) & (idx.year <= 2022)] *= 0.2
    x = pd.Series(y, index=idx, name="synthetic_weather")
    x.attrs = {"units": "mm/month", "cadence": "monthly", "variable": "precipitation",
               "source": "synthetic:test", "retrieved": "2026-11-15", "product": "synthetic",
               "version": "1", "spatial_support": {"kind": "synthetic"}, "quality": "known generator",
               "sha256": "synthetic-not-observations", "time_standard": "UTC", "lineage": ["synthetic"]}
    return x


def annual_precipitation_null(n: int, phi: float, seed: int, kind: str = "gamma") -> np.ndarray:
    """Labelled synthetic annual precipitation for calibration, never observed evidence.

    Gaussian-copula gamma/intermittent AR(1), or fractionally integrated noise
    (d=.35, finite 500-lag truncation) transformed to a gamma marginal.
    """
    from scipy import stats
    rng = np.random.default_rng(seed)
    size = n + 1000
    innovations = rng.normal(size=size)
    if kind == "long_memory":
        weights = np.ones(500)
        for k in range(1,len(weights)):
            weights[k] = weights[k-1]*(k-1+.35)/k
        latent = np.convolve(innovations,weights)[:size]/np.sqrt(weights @ weights)
    else:
        latent = np.empty(size)
        latent[0] = innovations[0]
        for i in range(1,size):
            latent[i] = phi*latent[i-1]+np.sqrt(1-phi**2)*innovations[i]
    probabilities = np.clip(stats.norm.cdf(latent[-n:]),1e-10,1-1e-10)
    if kind == "intermittent":
        return np.where(probabilities <= .25,0,stats.gamma.ppf(np.maximum((probabilities-.25)/.75,1e-10),a=1.5,scale=100))
    return stats.gamma.ppf(probabilities,a=3,scale=100)


def _provenance(variable: str, units: str, cadence: str, product: str, **extra) -> dict:
    """Metadata of the kind an adapter attaches, marked as synthetic."""
    return {"variable": variable, "units": units, "cadence": cadence, "product": product,
            "version": "synthetic", "source": "data/synthetic/generators.py", "retrieved": "2026-01-01",
            "sha256": "synthetic", "time_standard": "UTC", "quality": "synthetic",
            "spatial_support": {"kind": "synthetic"}, **extra}


def year_effects(n_years: int = 25, seed: int = 0) -> np.ndarray:
    """Standardized good-year / bad-year effects, to make rainfall and greenness move together in tests."""
    return np.random.default_rng(seed).normal(0, 1, n_years)


def ndvi_composites(n_years: int = 24, low_year: int | None = None, depth: float = 0.12, drift_per_year: float = 0.0,
                    sigma: float = 0.02, cloud: float = 0.05, seed: int = 0, start_year: int = 2001,
                    effects: np.ndarray | None = None) -> pd.Series:
    """16-day vegetation-index composites with one growing season a year (peak in July).

    `low_year` lowers that year's April-September greenness by `depth`; `cloud` is the
    share of composites lost (NaN). Dates restart on 1 January each year, as MODIS composites do.
    """
    rng = np.random.default_rng(seed)
    dates = [pd.Timestamp(year=y, month=1, day=1) + pd.Timedelta(days=16 * k) for y in range(start_year, start_year + n_years) for k in range(23)]
    idx = pd.DatetimeIndex(dates)
    doy = idx.day_of_year.to_numpy()
    season = np.clip(np.sin(np.pi * (doy - 90) / 200), 0, None)  # green from about April to mid-October
    drawn = rng.normal(0, 0.025, n_years)
    year_effect = dict(zip(range(start_year, start_year + n_years), drawn if effects is None else 0.03 * effects[:n_years]))
    values = 0.25 + (0.35 + np.array([year_effect[y] for y in idx.year])) * season
    values = values + drift_per_year * (idx.year - start_year) + rng.normal(0, sigma, len(idx))
    if low_year is not None:
        values = values - depth * season * (idx.year == low_year)
    values = np.where(rng.random(len(idx)) < cloud, np.nan, np.clip(values, -0.2, 1.0))
    out = pd.Series(values, index=idx, name="ndvi")
    out.attrs = _provenance("vegetation_index", "NDVI", "16-day composite", "synthetic vegetation index")
    return out


def daily_rain(n_years: int = 25, low_year: int | None = None, factor: float = 0.4, seed: int = 0,
               start_year: int = 2001, effects: np.ndarray | None = None) -> pd.Series:
    """Daily rainfall with a March-September wet season; `low_year` gets `factor` times the usual rain."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(f"{start_year}-01-01", f"{start_year + n_years - 1}-12-31", freq="D")
    wet = np.clip(np.sin(np.pi * (idx.day_of_year.to_numpy() - 60) / 215), 0.03, None)
    drawn = rng.gamma(40, 1 / 40, n_years)
    yearly = dict(zip(range(start_year, start_year + n_years), drawn if effects is None else np.exp(0.2 * effects[:n_years])))
    values = rng.gamma(0.6, 8, len(idx)) * (rng.random(len(idx)) < 0.5 * wet) * np.array([yearly[y] for y in idx.year])
    if low_year is not None:
        values = values * np.where(idx.year == low_year, factor, 1.0)
    out = pd.Series(values, index=idx, name="rain")
    out.attrs = _provenance("precipitation", "mm/day", "daily", "synthetic rainfall")
    return out


def monthly_rain(n_years: int = 27, seed: int = 0, start_year: int = 2000, mean: float = 60.0) -> pd.Series:
    """Monthly rainfall totals (mm) with a summer peak and year-to-year swings."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(f"{start_year}-01-01", periods=12 * n_years, freq="MS")
    shape = 1 + 0.9 * np.sin(2 * np.pi * (idx.month.to_numpy() - 4) / 12)
    yearly = np.repeat(rng.gamma(12, 1 / 12, n_years), 12)
    out = pd.Series(mean * shape * yearly * rng.gamma(6, 1 / 6, len(idx)), index=idx, name="rain")
    out.attrs = _provenance("precipitation", "mm/month", "monthly", "synthetic rainfall")
    return out


# Months without a solution in the NASA GSFC GRACE/GRACE-FO mascon record (April 2002 to June 2026), read from
# the product's own list of solution dates. Synthetic records copy this pattern so tests face the real gaps.
GRACE_MISSING = (
    "2002-06 2002-07 2003-06 2011-01 2011-06 2012-05 2012-10 2013-03 2013-08 2013-09 2014-02 2014-07 2014-12 "
    "2015-06 2015-10 2015-11 2016-04 2016-09 2016-10 2017-02 2017-07 2017-08 2017-09 2017-10 2017-11 2017-12 "
    "2018-01 2018-02 2018-03 2018-04 2018-05 2018-08 2018-09").split()


def water_storage(slope_per_year: float = 0.0, rain: pd.Series | None = None, response: float = 0.0, sigma: float = 1.0,
                  phi: float = 0.5, offset_at_handover: float = 0.0, cells: int = 26, kind: str = "total_water_storage",
                  seed: int = 0) -> pd.Series:
    """Monthly water-storage anomaly (cm), April 2002 to June 2026, with the real record's missing months.

    `slope_per_year` is a steady drift. With `rain` and `response`, storage also integrates
    rainfall departures (cm of storage per 100 mm of rain above average). `phi` sets
    month-to-month persistence of the noise; `offset_at_handover` adds a step from June 2018.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2002-04-01", "2026-06-01", freq="MS")
    t = np.arange(len(idx))
    noise = np.zeros(len(idx) + 200)
    for i in range(1, len(noise)):
        noise[i] = phi * noise[i - 1] + rng.normal(0, sigma)
    values = slope_per_year * t / 12 + 4 * np.sin(2 * np.pi * t / 12) + noise[200:]
    if rain is not None and response:
        departures = (rain - rain.groupby(rain.index.month).transform("mean")).reindex(idx).fillna(0.0)
        values = values + response * departures.cumsum().to_numpy() / 100.0
    values = values + offset_at_handover * (idx >= "2018-06-01")
    out = pd.Series(values, index=idx, name="storage")
    out[pd.to_datetime(GRACE_MISSING)] = np.nan
    out.attrs = _provenance("water_storage_anomaly", "cm equivalent water height", "monthly", "synthetic water storage",
                            storage_kind=kind, resolution_units=cells, min_resolution_units=22, area_km2=12400.0 * cells)
    if kind == "groundwater":
        out.attrs["subtraction"] = {"method": "synthetic: no subtraction performed", "model": "synthetic",
                                    "not_subtracted": "surface water (lakes, rivers, reservoirs, canals) was not subtracted, because the model has no such store"}
    return out
