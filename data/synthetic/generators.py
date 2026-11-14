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
