"""Phase 2 reproducible artifact builder with isolated synthetic and account lanes."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import lifelines
import numpy as np
import pandas as pd

from everpure_case.reactivation_scenarios import (
    ASSUMPTIONS_FILE,
    PRIMARY_POLICY,
    assumption_fingerprint,
    load_assumptions,
    load_phase1_accounts,
    project_accounts,
    reconcile_cohort,
    scenario_sensitivity,
)
from everpure_case.source_integrity import EXPECTED_SHA256
from everpure_case.survival import exponential_event_probability
from everpure_case.survival_synthetic import (
    BASELINE_HAZARD,
    COEFFICIENTS,
    N_SUBJECTS,
    SEED,
    fit_synthetic_cox,
    generate_synthetic_cohort,
    kaplan_meier,
)


def _json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )


def _csv(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False, encoding="utf-8", float_format="%.12g")


def _artifact_provenance(name: str) -> str | list[str]:
    if name.startswith("synthetic_"):
        return "SYNTHETIC_METHODOLOGY"
    if name == "cohort_reconciliation.csv":
        return "DERIVED_SOURCE"
    if name == "feature_dictionary.csv":
        return ["DERIVED_SOURCE", "ASSUMPTION_BASED_NOT_CALIBRATED"]
    if name == "metrics.json":
        return [
            "OBSERVED_SOURCE",
            "DERIVED_SOURCE",
            "SYNTHETIC_METHODOLOGY",
            "ASSUMPTION_BASED_NOT_CALIBRATED",
        ]
    return "ASSUMPTION_BASED_NOT_CALIBRATED"


def feature_dictionary() -> pd.DataFrame:
    rows = [
        (
            "health_red / health_yellow",
            "sfdc_health_score / health_clean",
            "Phase 1 maps Green, Yellow, Red; Missing/nan to unknown",
            "two indicators, Green reference",
            "binary",
            "unknown uses Green-reference contribution; health_unknown=1",
            "illustrative health association",
            "snapshot timing unknown; no observed outcomes",
        ),
        (
            "partner_managed_yes",
            "partner_managed / partner_managed_clean",
            "Phase 1 retains 1, 0, unknown",
            "1 versus 0 indicator",
            "binary",
            "unknown uses direct-reference contribution; partner_unknown=1",
            "illustrative ownership association",
            "ownership unresolved for many accounts",
        ),
        (
            "log1p_valid_tickets",
            "open_support_tickets / tickets_clean",
            "Phase 1 converts 999 to missing, preserves 0",
            "log(1+valid count)",
            "dimensionless",
            "missing uses zero-ticket-reference contribution; tickets_missing=1",
            "illustrative support burden",
            "no ticket timestamps or trajectory",
        ),
        (
            "is_child",
            "parent_account_id / root_account_id",
            "Phase 1 one-to-one resolved hierarchy",
            "parent ID present indicator",
            "binary",
            "missing mapping rejected",
            "illustrative hierarchy position",
            "root membership may induce dependence; no economic consolidation",
        ),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "feature",
            "source_field",
            "cleaning_rule",
            "transformation",
            "unit",
            "missing_value_treatment",
            "analytical_interpretation",
            "leakage_or_measurement_caveat",
        ],
    ).assign(assumption_status="ASSUMPTION_BASED_NOT_CALIBRATED")


def run_scenario_lane(repo_root: str | Path, output_dir: str | Path | None = None) -> dict:
    """Real-account lane can execute when synthetic fitting and fixtures are unavailable."""
    root = Path(repo_root).resolve()
    out = Path(output_dir) if output_dir is not None else root / "outputs/phase2"
    out.mkdir(parents=True, exist_ok=True)
    assumptions = load_assumptions(root)
    accounts = load_phase1_accounts(root)
    reconciliation = reconcile_cohort(accounts)
    detail, summary = project_accounts(accounts, assumptions, PRIMARY_POLICY)
    sensitivity = scenario_sensitivity(accounts, assumptions)
    counts = reconciliation.scenario_cohort_status.value_counts().to_dict()
    if counts != {
        "primary_reported_2y": 1144,
        "eligibility_conflict": 562,
        "eligibility_unknown": 294,
    }:
        raise AssertionError(f"Cohort reconciliation changed: {counts}")
    if (
        len(detail) != 1144 * 3 * 3
        or not detail.cumulative_reactivation_probability.between(0, 1).all()
    ):
        raise AssertionError("Primary scenario prediction grain or probability invalid")
    ordered = detail.pivot(
        index=["account_id", "horizon_months"],
        columns="scenario_name",
        values="cumulative_reactivation_probability",
    )
    if not ((ordered.conservative <= ordered.base) & (ordered.base <= ordered.optimistic)).all():
        raise AssertionError("Scenario ordering failed")
    across = detail.pivot(
        index=["account_id", "scenario_name"],
        columns="horizon_months",
        values="cumulative_reactivation_probability",
    )
    if not ((across[3] <= across[6]) & (across[6] <= across[12])).all():
        raise AssertionError("Horizon monotonicity failed")
    for row in summary.itertuples(index=False):
        subset = detail.loc[
            (detail.scenario_name == row.scenario_name)
            & (detail.horizon_months == row.horizon_months)
        ]
        if len(subset) != row.cohort_accounts or not np.isclose(
            subset.cumulative_reactivation_probability.sum(),
            row.expected_reactivations,
            rtol=0,
            atol=1e-9,
        ):
            raise AssertionError("Expected reactivations do not reconcile")
    _csv(out / "cohort_reconciliation.csv", reconciliation)
    _csv(out / "feature_dictionary.csv", feature_dictionary())
    _csv(out / "reactivation_scenario_probabilities.csv", detail)
    _csv(out / "reactivation_scenario_summary.csv", summary)
    _csv(out / "scenario_sensitivity.csv", sensitivity)
    _json(out / "assumptions.json", assumptions)
    contract = {
        "version": "phase2-to-phase3-v2",
        "artifact": "outputs/phase2/reactivation_scenario_probabilities.csv",
        "grain": ["account_id", "scenario_name", "horizon_months"],
        "expected_rows": 10296,
        "expected_accounts": 1144,
        "account_identifier": "account_id",
        "root_identifier": "root_account_id",
        "cohort_policy": PRIMARY_POLICY,
        "cohort_status": "primary_reported_2y",
        "analysis_as_of_date": "2026-10-09",
        "time_unit": "continuous_month",
        "horizons_months": [3, 6, 12],
        "scenarios": ["conservative", "base", "optimistic"],
        "probability_definition": "P(reactivation by horizon from assumed 2026-10-09 origin)",
        "probability_column": "cumulative_reactivation_probability",
        "probability_range_inclusive": [0, 1],
        "probability_provenance": "ASSUMPTION_BASED_NOT_CALIBRATED",
        "account_identifier_provenance": "OBSERVED_SOURCE",
        "parameter_version": assumptions["version"],
        "assumption_register_artifact": "outputs/phase2/assumptions.json",
        "assumption_fingerprint_sha256": assumption_fingerprint(assumptions),
        "probability_artifact_sha256": hashlib.sha256(
            (out / "reactivation_scenario_probabilities.csv").read_bytes()
        ).hexdigest(),
        "summary_artifact_sha256": hashlib.sha256(
            (out / "reactivation_scenario_summary.csv").read_bytes()
        ).hexdigest(),
        "assumption_fingerprint_canonicalization": (
            "SHA-256 of UTF-8 JSON with sorted keys, compact separators, "
            "ensure_ascii=False and no NaN"
        ),
        "source_sha256": EXPECTED_SHA256,
        "reconcile_to": "outputs/phase2/reactivation_scenario_summary.csv",
        "summary_rule": (
            "expected_reactivations=sum(cumulative_reactivation_probability) "
            "by scenario_name,horizon_months"
        ),
        "observed_conversions": False,
        "fiscal_eligibility_confirmed": False,
        "event_semantics": {
            "horizon_probabilities": "cumulative first-reactivation probabilities",
            "sum_across_horizons": False,
            "independent_horizon_sampling": False,
            "events_per_account_per_path_max": 1,
            "coherent_first_event_time": (
                "May be sampled from the assumed constant account hazard; "
                "nested horizon indicators then follow from that time"
            ),
        },
        "scenario_semantics": {
            "kind": "fixed assumed cases",
            "mutually_exclusive_outcomes": False,
            "empirical_probability_weights_available": False,
            "confidence_intervals": False,
            "random_scenario_sampling_requires_new_explicit_weights": True,
        },
        "causal_attribution": {
            "observed_treatment_status": False,
            "untreated_counterfactual_available": False,
            "gross_reactivation_is_incremental_uplift": False,
            "without_counterfactual_valuation_label": ("illustrative gross reactivation economics"),
            "incremental_cash_flow_requires_additional_assumptions": True,
        },
        "hierarchy_semantics": {
            "within_root_outcomes_may_be_correlated": True,
            "phase3_dependence_assumption_required": True,
            "automatic_parent_child_spend_summation_allowed": False,
        },
        "time_basis": {
            "unit": "continuous_month",
            "calendar_date_mapping_required": True,
            "exact_calendar_deadline_claim_without_mapping_allowed": False,
            "financial_discounting_convention_required": True,
        },
    }
    validate_phase3_contract(contract, assumptions, detail, summary)
    _json(out / "phase3_input_contract.json", contract)
    validate_phase3_artifacts(out)
    return {
        "provenance": "ASSUMPTION_BASED_NOT_CALIBRATED",
        "cohort_counts": counts,
        "primary_prediction_rows": len(detail),
        "primary_accounts": 1144,
        "scenario_summary": summary.to_dict(orient="records"),
        "probability_min": float(detail.cumulative_reactivation_probability.min()),
        "probability_max": float(detail.cumulative_reactivation_probability.max()),
    }


def validate_phase3_contract(
    contract: dict, assumptions: dict, detail: pd.DataFrame, summary: pd.DataFrame
) -> None:
    """Fail if a stale contract or altered assumption register reaches Phase 3."""
    if contract.get("version") != "phase2-to-phase3-v2":
        raise ValueError("Unsupported Phase 3 contract version")
    if contract.get("assumption_fingerprint_sha256") != assumption_fingerprint(assumptions):
        raise ValueError("Phase 3 assumption fingerprint mismatch")
    if contract.get("parameter_version") != assumptions["version"]:
        raise ValueError("Phase 3 assumption version mismatch")
    key = contract["grain"]
    if (
        len(detail) != contract["expected_rows"]
        or detail.account_id.nunique() != contract["expected_accounts"]
        or detail.duplicated(key).any()
        or not detail.cumulative_reactivation_probability.between(0, 1).all()
    ):
        raise ValueError("Phase 3 probability grain or bounds mismatch")
    if not detail.scenario_parameter_version.eq(contract["parameter_version"]).all():
        raise ValueError("Phase 3 detail parameter version mismatch")
    if not detail.probability_provenance.eq(contract["probability_provenance"]).all():
        raise ValueError("Phase 3 probability provenance mismatch")
    if set(detail.scenario_name) != set(contract["scenarios"]) or set(detail.horizon_months) != set(
        contract["horizons_months"]
    ):
        raise ValueError("Phase 3 scenario or horizon mismatch")
    expected_hazards = detail.scenario_name.map(assumptions["monthly_baseline_hazards"])
    if not np.allclose(detail.assumed_baseline_hazard_per_month, expected_hazards):
        raise ValueError("Phase 3 assumed baseline mismatch")
    computed = exponential_event_probability(
        detail.assumed_baseline_hazard_per_month.to_numpy(),
        detail.horizon_months.to_numpy(),
        detail.assumed_log_hazard_linear_predictor.to_numpy(),
    )
    if not np.allclose(
        detail.cumulative_reactivation_probability.to_numpy(), computed, rtol=0, atol=2e-11
    ):
        raise ValueError("Phase 3 cumulative probability formula mismatch")
    for row in summary.itertuples(index=False):
        values = detail.loc[
            detail.scenario_name.eq(row.scenario_name)
            & detail.horizon_months.eq(row.horizon_months),
            "cumulative_reactivation_probability",
        ]
        if len(values) != row.cohort_accounts or not np.isclose(
            values.sum(), row.expected_reactivations, rtol=0, atol=1e-9
        ):
            raise ValueError("Phase 3 summary reconciliation mismatch")


def validate_phase3_artifacts(output_dir: str | Path) -> None:
    """Validate local files against the contract before downstream consumption."""
    out = Path(output_dir)
    contract = json.loads((out / "phase3_input_contract.json").read_text(encoding="utf-8"))
    assumptions = json.loads((out / "assumptions.json").read_text(encoding="utf-8"))
    for filename, key in (
        ("reactivation_scenario_probabilities.csv", "probability_artifact_sha256"),
        ("reactivation_scenario_summary.csv", "summary_artifact_sha256"),
    ):
        if hashlib.sha256((out / filename).read_bytes()).hexdigest() != contract.get(key):
            raise ValueError(f"Phase 3 artifact hash mismatch: {filename}")
    detail = pd.read_csv(out / "reactivation_scenario_probabilities.csv")
    summary = pd.read_csv(out / "reactivation_scenario_summary.csv")
    validate_phase3_contract(contract, assumptions, detail, summary)


def run_pipeline(repo_root: str | Path, output_dir: str | Path | None = None) -> dict:
    root = Path(repo_root).resolve()
    out = Path(output_dir) if output_dir is not None else root / "outputs/phase2"
    # The lanes share only the output directory and generic survival mathematics.
    account_metrics = run_scenario_lane(root, out)
    synthetic = generate_synthetic_cohort()
    model, coefficients, diagnostic, predictions = fit_synthetic_cox(synthetic)
    synthetic_observed = synthetic.drop(columns=["true_event_time_months", "censor_time_months"])
    _csv(out / "synthetic_survival_cohort.csv", synthetic_observed)
    _csv(out / "synthetic_cox_coefficients.csv", coefficients)
    _csv(out / "synthetic_survival_predictions.csv", predictions)
    _csv(out / "synthetic_kaplan_meier.csv", kaplan_meier(synthetic))
    _csv(
        out / "synthetic_baseline_survival.csv",
        model.baseline_survival_.reset_index().rename(
            columns={"index": "duration_months", "baseline survival": "survival_probability"}
        ),
    )
    _json(out / "synthetic_model_diagnostics.json", diagnostic)
    synthetic_manifest = {
        "provenance": "SYNTHETIC_METHODOLOGY",
        "seed": SEED,
        "subjects": N_SUBJECTS,
        "events": diagnostic["n_events"],
        "right_censored": diagnostic["n_right_censored"],
        "event_fraction": diagnostic["n_events"] / N_SUBJECTS,
        "duration_min_months": float(synthetic.duration_months.min()),
        "duration_max_months": float(synthetic.duration_months.max()),
        "duration_median_months": float(synthetic.duration_months.median()),
        "baseline_hazard_per_month": BASELINE_HAZARD,
        "true_generating_coefficients": COEFFICIENTS,
        "covariates": (
            "health_proxy~Bernoulli(.4); engagement_proxy~Normal(0,1); partner_proxy~Bernoulli(.5)"
        ),
        "censoring": "independent Uniform(8,48) months capped at 36 months",
        "study_origin": "synthetic enrollment t=0",
        "month_definition": "continuous simulation time unit",
    }
    _json(out / "synthetic_generation_manifest.json", synthetic_manifest)
    metrics = {
        "source_sha256": EXPECTED_SHA256,
        "analysis_as_of_date": "2026-10-09",
        "account_scenarios": account_metrics,
        "synthetic_cox": {
            "provenance": "SYNTHETIC_METHODOLOGY",
            "generation": synthetic_manifest,
            "diagnostics": diagnostic,
            "coefficients": coefficients.to_dict(orient="records"),
        },
    }
    _json(out / "metrics.json", metrics)
    files = sorted(p for p in out.iterdir() if p.is_file() and p.name != "manifest.json")
    manifest = {
        "version": "phase2-artifact-manifest-v1",
        "source_sha256": EXPECTED_SHA256,
        "source_provenance": "OBSERVED_SOURCE",
        "assumption_register": ASSUMPTIONS_FILE,
        "assumption_version": load_assumptions(root)["version"],
        "analysis_as_of_date": "2026-10-09",
        "time_unit": "continuous_month",
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "lifelines_version": lifelines.__version__,
        "files": [
            {
                "name": p.name,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "provenance": _artifact_provenance(p.name),
            }
            for p in files
        ],
    }
    _json(out / "manifest.json", manifest)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Phase 2 synthetic Cox and assumed scenarios"
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    metrics = run_pipeline(args.repo_root)
    print(
        json.dumps(
            {
                "primary_accounts": metrics["account_scenarios"]["primary_accounts"],
                "synthetic_events": metrics["synthetic_cox"]["diagnostics"]["n_events"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
