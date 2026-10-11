"""Synthetic event histories and genuine Cox fitting; never imports account data."""

import warnings

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, KaplanMeierFitter
from lifelines.exceptions import ConvergenceError, ConvergenceWarning
from lifelines.statistics import proportional_hazard_test
from lifelines.utils import concordance_index

PROVENANCE = "SYNTHETIC_METHODOLOGY"
SEED = 20261009
COEFFICIENTS = {"health_proxy": 0.45, "engagement_proxy": -0.35, "partner_proxy": 0.25}
BASELINE_HAZARD = 0.035
N_SUBJECTS = 1600
FOLLOWUP_MONTHS = 36.0
MODEL_COLUMNS = ["duration_months", "event_observed", *COEFFICIENTS]


class SyntheticCoxFitError(RuntimeError):
    """A hard Cox fitting failure, distinct from a returned unstable fit."""

    fit_status = "hard_failure"

    def __init__(self, message: str, captured_warnings: list[str] | None = None) -> None:
        super().__init__(message)
        self.captured_warnings = captured_warnings or []


def generate_synthetic_cohort(n: int = N_SUBJECTS, seed: int = SEED) -> pd.DataFrame:
    """Exponential PH events with independent administrative/random censoring.

    One month is a continuous simulation time unit, not a calendar month.
    Enrollment at t=0 is synthetic and unrelated to the Everpure analysis date.
    """
    if n < 1:
        raise ValueError("Synthetic cohort must contain subjects")
    rng = np.random.default_rng(seed)
    health = rng.binomial(1, 0.4, n)
    engagement = rng.normal(0, 1, n)
    partner = rng.binomial(1, 0.5, n)
    lp = (
        COEFFICIENTS["health_proxy"] * health
        + COEFFICIENTS["engagement_proxy"] * engagement
        + COEFFICIENTS["partner_proxy"] * partner
    )
    event_time = rng.exponential(1 / (BASELINE_HAZARD * np.exp(lp)))
    censor_time = np.minimum(rng.uniform(8, 48, n), FOLLOWUP_MONTHS)
    return pd.DataFrame(
        {
            "synthetic_subject_id": [f"SYN_{i:05d}" for i in range(n)],
            "duration_months": np.minimum(event_time, censor_time),
            "event_observed": (event_time <= censor_time).astype(int),
            "health_proxy": health,
            "engagement_proxy": engagement,
            "partner_proxy": partner,
            "true_event_time_months": event_time,
            "censor_time_months": censor_time,
            "provenance": PROVENANCE,
        }
    )


def validate_observed_history(frame: pd.DataFrame) -> None:
    required = {"synthetic_subject_id", *MODEL_COLUMNS}
    if not required <= set(frame):
        raise ValueError(f"Missing synthetic history columns: {required - set(frame)}")
    if frame.synthetic_subject_id.isna().any() or not frame.synthetic_subject_id.is_unique:
        raise ValueError("Synthetic subject IDs must be present and unique")
    if not frame.synthetic_subject_id.astype(str).str.startswith("SYN_").all():
        raise ValueError("Only synthetic IDs may enter Cox fitting")
    matrix = frame[MODEL_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(matrix).all() or (frame.duration_months <= 0).any():
        raise ValueError("Observed durations and covariates must be positive/finite")
    if not frame.event_observed.isin([0, 1]).all():
        raise ValueError("Event indicator must be binary")
    covariates = frame[list(COEFFICIENTS)].to_numpy(dtype=float)
    if np.linalg.matrix_rank(covariates - covariates.mean(axis=0)) != len(COEFFICIENTS):
        raise ValueError("Covariates are rank deficient")
    if np.linalg.cond(covariates - covariates.mean(axis=0)) > 1e6:
        raise ValueError("Covariates are ill conditioned")


def fit_synthetic_cox(frame: pd.DataFrame) -> tuple[CoxPHFitter, pd.DataFrame, dict, pd.DataFrame]:
    """Fit only observable durations/events/covariates; truth columns cannot enter."""
    validate_observed_history(frame)
    if frame.event_observed.sum() == 0:
        raise ValueError("Cox fitting requires observed events")
    observed = frame[MODEL_COLUMNS].copy()
    caught = []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model = CoxPHFitter()
            model.fit(observed, duration_col="duration_months", event_col="event_observed")
            diagnostic = proportional_hazard_test(model, observed, time_transform="rank")
    except (ConvergenceError, np.linalg.LinAlgError, FloatingPointError) as exc:
        raise SyntheticCoxFitError(
            f"Cox hard numerical failure: {exc}", [str(w.message) for w in caught]
        ) from exc
    summary = model.summary.reset_index().rename(columns={"covariate": "covariate"})
    coefficients = summary[
        ["covariate", "coef", "exp(coef)", "se(coef)", "exp(coef) lower 95%", "exp(coef) upper 95%"]
    ].rename(
        columns={
            "coef": "estimated_log_hazard_coefficient",
            "exp(coef)": "estimated_hazard_ratio",
            "se(coef)": "standard_error",
            "exp(coef) lower 95%": "hazard_ratio_ci_lower_95",
            "exp(coef) upper 95%": "hazard_ratio_ci_upper_95",
        }
    )
    coefficients["true_generating_coefficient"] = coefficients.covariate.map(COEFFICIENTS)
    if not np.isfinite(
        coefficients[
            [
                "estimated_log_hazard_coefficient",
                "estimated_hazard_ratio",
                "standard_error",
                "hazard_ratio_ci_lower_95",
                "hazard_ratio_ci_upper_95",
            ]
        ].to_numpy()
    ).all():
        raise SyntheticCoxFitError(
            "Cox hard numerical failure: non-finite fitted estimates",
            [str(w.message) for w in caught],
        )
    coefficients["interpretation"] = np.where(
        coefficients.estimated_log_hazard_coefficient > 0,
        "higher instantaneous hazard",
        "lower instantaneous hazard",
    )
    coefficients["provenance"] = PROVENANCE
    ph = {str(k): float(v) for k, v in diagnostic.summary.p.to_dict().items()}
    baseline = model.baseline_survival_.iloc[:, 0]
    if not baseline.between(0, 1).all() or (baseline.diff().dropna() > 1e-12).any():
        raise AssertionError("Baseline survival must decrease within [0,1]")
    holdout = generate_synthetic_cohort(400, SEED + 1)
    holdout_risk = model.predict_partial_hazard(holdout[list(COEFFICIENTS)]).to_numpy().ravel()
    convergence_warnings = [
        str(w.message) for w in caught if issubclass(w.category, ConvergenceWarning)
    ]
    numerical_warnings = [str(w.message) for w in caught if issubclass(w.category, RuntimeWarning)]
    stable_fit = not convergence_warnings and not numerical_warnings
    diagnostics = {
        "provenance": PROVENANCE,
        "converged": stable_fit,
        "fit_status": "converged" if stable_fit else "warning_unstable",
        "warnings": [str(w.message) for w in caught],
        "convergence_warnings": convergence_warnings,
        "numerical_warnings": numerical_warnings,
        "ph_schoenfeld_rank_p_values": ph,
        "ph_rejections_at_0_05": [k for k, p in ph.items() if p < 0.05],
        "concordance_in_sample": float(model.concordance_index_),
        "concordance_independent_synthetic_holdout": float(
            concordance_index(holdout.duration_months, -holdout_risk, holdout.event_observed)
        ),
        "baseline_survival_monotone": True,
        "baseline_survival_at_last_event": float(baseline.iloc[-1]),
        "baseline_survival_reference_profile": "lifelines mean covariate profile",
        "n_events": int(frame.event_observed.sum()),
        "n_right_censored": int((1 - frame.event_observed).sum()),
    }
    profiles = pd.DataFrame(
        [
            {"health_proxy": 0, "engagement_proxy": 0, "partner_proxy": 0},
            {"health_proxy": 1, "engagement_proxy": 0, "partner_proxy": 1},
            {"health_proxy": 0, "engagement_proxy": 1, "partner_proxy": 0},
        ]
    )
    times = [3.0, 6.0, 12.0, 24.0, 36.0]
    curves = model.predict_survival_function(profiles, times=times)
    predictions = pd.DataFrame(
        [
            {
                "synthetic_profile_id": f"PROFILE_{j + 1}",
                "horizon_months": t,
                "survival_probability": float(curves.loc[t, j]),
                "cumulative_event_probability": float(1 - curves.loc[t, j]),
                "provenance": PROVENANCE,
            }
            for j in range(len(profiles))
            for t in times
        ]
    )
    if not predictions.survival_probability.between(0, 1).all():
        raise AssertionError("Synthetic survival prediction out of range")
    return model, coefficients, diagnostics, predictions


def kaplan_meier(frame: pd.DataFrame) -> pd.DataFrame:
    validate_observed_history(frame)
    km = KaplanMeierFitter().fit(frame.duration_months, frame.event_observed)
    return km.survival_function_.reset_index().rename(
        columns={"timeline": "duration_months", "KM_estimate": "survival_probability"}
    )
