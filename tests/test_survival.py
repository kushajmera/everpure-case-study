import warnings

import numpy as np
import pytest
from lifelines.exceptions import ConvergenceError, ConvergenceWarning

import everpure_case.survival_synthetic as synthetic_module
from everpure_case.survival import exponential_event_probability
from everpure_case.survival_synthetic import (
    COEFFICIENTS,
    SyntheticCoxFitError,
    fit_synthetic_cox,
    generate_synthetic_cohort,
    validate_observed_history,
)


def test_exponential_survival_known_values_and_tails():
    assert exponential_event_probability(0.02, 0, 0) == 0
    assert exponential_event_probability(0, 12, 0) == 0
    assert exponential_event_probability(0.02, 12, 0) == pytest.approx(1 - np.exp(-0.24))
    assert exponential_event_probability(1e300, 12, 0) == 1
    assert exponential_event_probability(0.02, 12, np.log(2)) == pytest.approx(1 - np.exp(-0.48))
    p = exponential_event_probability(0.02, np.array([3, 6, 12]), 0)
    assert np.all(np.diff(p) > 0)


@pytest.mark.parametrize(
    "hazard,horizon,lp", [(-0.1, 1, 0), (0.1, -1, 0), (0.1, 1, np.nan), (np.inf, 1, 0)]
)
def test_exponential_survival_rejects_invalid_input(hazard, horizon, lp):
    with pytest.raises(ValueError):
        exponential_event_probability(hazard, horizon, lp)


def test_synthetic_generation_is_reproducible_and_censoring_coherent():
    a = generate_synthetic_cohort(300)
    b = generate_synthetic_cohort(300)
    assert a.equals(b)
    assert a.synthetic_subject_id.is_unique
    assert a.synthetic_subject_id.str.startswith("SYN_").all()
    assert (a.true_event_time_months > 0).all()
    assert (a.censor_time_months > 0).all()
    assert np.allclose(
        a.duration_months, np.minimum(a.true_event_time_months, a.censor_time_months)
    )
    assert a.event_observed.eq(a.true_event_time_months.le(a.censor_time_months)).all()
    assert not a.to_csv(index=False).count("ACC_")


def test_fitting_uses_only_observed_columns_and_reports_diagnostics():
    frame = generate_synthetic_cohort(800)
    model, coefficients, diagnostics, predictions = fit_synthetic_cox(frame)
    assert set(model.params_.index) == set(COEFFICIENTS)
    assert "true_event_time_months" not in model.params_.index
    assert "censor_time_months" not in model.params_.index
    assert diagnostics["n_events"] + diagnostics["n_right_censored"] == 800
    assert set(diagnostics["ph_schoenfeld_rank_p_values"]) == set(COEFFICIENTS)
    assert diagnostics["converged"]
    assert diagnostics["fit_status"] == "converged"
    assert not diagnostics["convergence_warnings"]
    assert coefficients.estimated_hazard_ratio.gt(0).all()
    assert predictions.cumulative_event_probability.between(0, 1).all()


def test_synthetic_validation_rejects_bad_records_and_all_censored_fit():
    a = generate_synthetic_cohort(150)
    for column, value in [
        ("duration_months", 0),
        ("event_observed", 2),
        ("health_proxy", np.nan),
        ("synthetic_subject_id", "UNRELATED_TEST_ID"),
    ]:
        broken = a.copy()
        broken.loc[0, column] = value
        with pytest.raises(ValueError):
            validate_observed_history(broken)
    duplicate = a.copy()
    duplicate.loc[1, "synthetic_subject_id"] = duplicate.loc[0, "synthetic_subject_id"]
    with pytest.raises(ValueError):
        validate_observed_history(duplicate)
    censored = a.assign(event_observed=0)
    validate_observed_history(censored)
    with pytest.raises(ValueError, match="requires observed events"):
        fit_synthetic_cox(censored)


def test_separation_sample_is_hard_failure_with_warning_evidence():
    frame = generate_synthetic_cohort(250)
    frame["health_proxy"] = frame.event_observed
    with pytest.raises(SyntheticCoxFitError, match="non-finite fitted estimates") as error:
        fit_synthetic_cox(frame)
    assert error.value.fit_status == "hard_failure"
    assert any("separation" in warning.lower() for warning in error.value.captured_warnings)


def test_convergence_warning_does_not_report_success(monkeypatch):
    original_fit = synthetic_module.CoxPHFitter.fit

    def fit_with_warning(self, *args, **kwargs):
        warnings.warn("deliberate instability", ConvergenceWarning, stacklevel=1)
        return original_fit(self, *args, **kwargs)

    monkeypatch.setattr(synthetic_module.CoxPHFitter, "fit", fit_with_warning)
    _, _, diagnostics, _ = fit_synthetic_cox(generate_synthetic_cohort(250))
    assert not diagnostics["converged"]
    assert diagnostics["fit_status"] == "warning_unstable"
    assert any("deliberate instability" in w for w in diagnostics["convergence_warnings"])


def test_hard_numerical_failure_is_distinct(monkeypatch):
    def failed_fit(*_args, **_kwargs):
        raise ConvergenceError("deliberate numerical failure")

    monkeypatch.setattr(synthetic_module.CoxPHFitter, "fit", failed_fit)
    with pytest.raises(SyntheticCoxFitError, match="hard numerical failure") as error:
        fit_synthetic_cox(generate_synthetic_cohort(150))
    assert error.value.fit_status == "hard_failure"
