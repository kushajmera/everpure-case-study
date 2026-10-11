"""Shared survival mathematics; no fitted model or business assumptions live here."""

import numpy as np


def exponential_event_probability(
    baseline_hazard_per_month: float | np.ndarray,
    horizon_months: float | np.ndarray,
    log_hazard_ratio: float | np.ndarray,
) -> np.ndarray:
    """Return 1-exp(-lambda*t*exp(lp)), with checked inputs and stable tails."""
    hazard, horizon, lp = np.broadcast_arrays(
        np.asarray(baseline_hazard_per_month, dtype=float),
        np.asarray(horizon_months, dtype=float),
        np.asarray(log_hazard_ratio, dtype=float),
    )
    if not all(np.isfinite(x).all() for x in (hazard, horizon, lp)):
        raise ValueError("Survival inputs must be finite")
    if (hazard < 0).any() or (horizon < 0).any():
        raise ValueError("Hazard and horizon must be nonnegative")
    # Above log(745), exp(-cumulative hazard) is indistinguishable from zero.
    log_cumulative = np.full(hazard.shape, -np.inf)
    positive = (hazard > 0) & (horizon > 0)
    with np.errstate(over="ignore"):
        log_cumulative[positive] = (
            np.log(hazard[positive]) + np.log(horizon[positive]) + lp[positive]
        )
        cumulative = np.exp(np.minimum(log_cumulative, np.log(745.0)))
    return np.clip(-np.expm1(-cumulative), 0.0, 1.0)
