"""Build the assumption-conditional Phase 3 financial scenario artifacts."""

import argparse
import copy
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd

from everpure_case.financial_model import (
    SCENARIOS,
    account_expectation,
    event_times,
    fingerprint,
    load_assumptions,
    pathwise,
    summarize,
)
from everpure_case.phase2_pipeline import validate_phase3_artifacts as validate_phase2_artifacts
from everpure_case.reactivation_scenarios import load_phase1_accounts
from everpure_case.source_integrity import EXPECTED_SHA256, verify_authoritative_source

PROVENANCE = "ASSUMPTION_BASED_NOT_CALIBRATED"
LABEL = "ILLUSTRATIVE_NET_PROGRAM_NPV_NOT_CAUSALLY_ATTRIBUTED"
Z_LIMIT = 4.5  # Predeclared conservative simultaneous nine-cell diagnostic.
AGGREGATE_ARTIFACTS = frozenset(
    {
        "financial_assumptions.json",
        "financial_scenario_matrix.csv",
        "monte_carlo_run_results.csv",
        "monte_carlo_npv_summary.csv",
        "monthly_cashflow_summary.csv",
        "financial_sensitivity.csv",
        "discount_break_even.csv",
        "financial_reconciliation.json",
        "phase4_input_contract.json",
        "metrics.json",
    }
)
FIGURE_ARTIFACTS = frozenset(
    {
        "break_even_economics.png",
        "financial_pv_bridge.png",
        "financial_sensitivity.png",
        "nine_cell_comparison.png",
        "npv_distribution.png",
        "npv_risk_ranges.png",
    }
)


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    # Seventeen significant digits preserve binary64 values on CSV round-trip.
    frame.to_csv(path, index=False, float_format="%.17g")


def financial_tolerance(scale: np.ndarray | float) -> np.ndarray:
    """Allow floating summation/CSV error while rejecting sub-cent corruption.

    The relative term exceeds binary64 round-trip and 1,144-row summation noise;
    the $0.001 ceiling keeps even large portfolio checks below one cent.
    """
    magnitude = np.maximum(1.0, np.abs(np.asarray(scale, dtype=float)))
    return np.minimum(0.001, 1e-8 + 2e-12 * magnitude)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs(root: Path) -> tuple[dict, dict, pd.DataFrame, pd.DataFrame]:
    verify_authoritative_source(root)
    phase2 = root / "outputs/phase2"
    validate_phase2_artifacts(phase2)
    contract = json.loads((phase2 / "phase3_input_contract.json").read_text(encoding="utf-8"))
    if (
        contract["source_sha256"] != EXPECTED_SHA256
        or contract["expected_accounts"] != 1144
        or contract["expected_rows"]
        != contract["expected_accounts"]
        * len(contract["scenarios"])
        * len(contract["horizons_months"])
        or contract["horizons_months"] != [3, 6, 12]
        or contract["scenarios"] != list(SCENARIOS)
    ):
        raise ValueError("Frozen Phase 2 contract mismatch")
    assumptions = load_assumptions(root, contract)
    detail = pd.read_csv(
        phase2 / "reactivation_scenario_probabilities.csv",
        dtype={"account_id": str, "root_account_id": str},
    )
    accounts = load_phase1_accounts(root)
    metrics = json.loads((root / "outputs/phase1/metrics.json").read_text(encoding="utf-8"))
    required_counts = {
        "unique_account_ids": 2000,
        "root_account_rows": 301,
        "direct_child_rows": 1699,
        "raw_recorded_spend_usd": 2541024291,
        "quality_exception_rows": 4889,
        "reported_2y_eligible_rows": 1144,
        "eligibility_disagreement_rows": 562,
        "reported_inactivity_missing_rows": 294,
    }
    if any(metrics.get(key) != value for key, value in required_counts.items()):
        raise ValueError("Phase 1 invariant mismatch")
    base = detail.loc[(detail.scenario_name == "base") & (detail.horizon_months == 12)].copy()
    base = base.sort_values(["account_id", "root_account_id"]).reset_index(drop=True)
    if (
        len(base) != contract["expected_accounts"]
        or base.account_id.duplicated().any()
        or base.root_account_id.isna().any()
    ):
        raise ValueError("Invalid primary account grain")
    if not base.scenario_cohort_status.eq("primary_reported_2y").all():
        raise ValueError("Primary cohort status mismatch")
    source = accounts[
        [
            "account_id",
            "root_account_id",
            "has_manual_review_exceptions",
            "eligibility_comparison_status",
        ]
    ]
    base = base.merge(source, on=["account_id", "root_account_id"], validate="one_to_one")
    if (
        len(base) != contract["expected_accounts"]
        or not base.eligibility_comparison_status.eq("agree_eligible").all()
    ):
        raise ValueError("Source qualification join mismatch")
    return contract, assumptions, detail, base


def _scenario_hazards(detail: pd.DataFrame, base: pd.DataFrame, scenario: str) -> np.ndarray:
    rows = detail.loc[(detail.scenario_name == scenario) & (detail.horizon_months == 12)]
    rows = rows.sort_values(["account_id", "root_account_id"]).reset_index(drop=True)
    if (
        not rows.account_id.equals(base.account_id)
        or not rows.root_account_id.equals(base.root_account_id)
        or not np.allclose(
            rows.assumed_log_hazard_linear_predictor,
            base.assumed_log_hazard_linear_predictor,
            rtol=0,
            atol=1e-12,
        )
    ):
        raise ValueError("Phase 2 scenario account alignment mismatch")
    hazards = rows.assumed_baseline_hazard_per_month.to_numpy() * np.exp(
        rows.assumed_log_hazard_linear_predictor.to_numpy()
    )
    for month in (3, 6, 12):
        supplied = detail.loc[(detail.scenario_name == scenario) & (detail.horizon_months == month)]
        supplied = supplied.sort_values(["account_id", "root_account_id"])
        if not np.allclose(
            -np.expm1(-hazards * month),
            supplied.cumulative_reactivation_probability.to_numpy(),
            rtol=0,
            atol=2e-11,
        ):
            raise ValueError("Phase 2 event probability identity failed")
    return hazards


def _expected_npv(
    hazards: np.ndarray, a: dict, tier_rate: float, *, retention: int | None = None
) -> float:
    return float(
        account_expectation(
            hazards, a, tier_rate, retention_paid_months=retention
        ).expected_account_npv.sum()
    )


def financial_sensitivity(hazards: np.ndarray, a: dict) -> pd.DataFrame:
    tier = a["commercial_discount_tiers"]["medium_15pct"]
    baseline = _expected_npv(hazards, a, tier)
    cases = [("baseline", "none", 1.0, {}, tier, hazards, None)]
    for field, multipliers in (
        ("monthly_gross_revenue_per_reactivated_account", (0.75, 1.25)),
        ("contribution_margin", (0.75, 1.25)),
        ("outreach_cost_per_target", (0.5, 1.5)),
        ("activation_cost_per_reactivation", (0.5, 1.5)),
    ):
        for factor in multipliers:
            cases.append(
                (
                    f"{field}_{factor:g}x",
                    field,
                    factor,
                    {field: a[field] * factor},
                    tier,
                    hazards,
                    None,
                )
            )
    for rate in (0.0, 0.24):
        cases.append(
            (
                f"financial_rate_{rate:g}",
                "annual_effective_financial_discount_rate",
                rate,
                {"annual_effective_financial_discount_rate": rate},
                tier,
                hazards,
                None,
            )
        )
    for name in ("low_5pct", "medium_15pct", "high_30pct"):
        rate = a["commercial_discount_tiers"][name]
        cases.append((f"commercial_{name}", "commercial_discount", rate, {}, rate, hazards, None))
    for factor in (0.5, 1.5):
        cases.append(
            (f"hazard_{factor:g}x", "hazard_multiplier", factor, {}, tier, hazards * factor, None)
        )
    for months in (3, 6):
        cases.append(
            (
                f"retention_cap_{months}_paid_months",
                "retention_paid_months",
                months,
                {},
                tier,
                hazards,
                months,
            )
        )
    cases.append(
        (
            "combined_adverse_hypothetical",
            "combined_assumptions",
            "see altered_inputs_json",
            {
                "monthly_gross_revenue_per_reactivated_account": 750.0,
                "contribution_margin": 0.45,
                "outreach_cost_per_target": 150.0,
                "activation_cost_per_reactivation": 300.0,
                "annual_effective_financial_discount_rate": 0.24,
            },
            tier,
            hazards,
            3,
        )
    )
    rows = []
    for name, changed, value, edits, discount, h, retention in cases:
        altered = copy.deepcopy(a)
        altered.update(edits)
        result = _expected_npv(h, altered, discount, retention=retention)
        rows.append(
            {
                "sensitivity_case": name,
                "changed_parameter": changed,
                "changed_value_or_factor": value,
                "base_scenario": "base",
                "base_commercial_discount": tier,
                "modeled_accounts": len(hazards),
                "baseline_expected_npv": baseline,
                "expected_npv": result,
                "difference_from_baseline": result - baseline,
                "altered_inputs_json": json.dumps(
                    {
                        **edits,
                        "commercial_discount": discount,
                        "hazard_multiplier": float(h[0] / hazards[0]),
                        "retention_paid_months": retention,
                    },
                    sort_keys=True,
                ),
                "provenance": PROVENANCE,
            }
        )
    return pd.DataFrame(rows)


def break_even(hazards: np.ndarray, a: dict) -> pd.DataFrame:
    low = a["commercial_discount_tiers"]["low_5pct"]
    account = account_expectation(hazards, a, low)
    paid_factor = float(account.paid_month_pv_factor.sum())
    activation_factor = float(account.activation_discount_factor_integral.sum())
    n = len(hazards)
    r = a["monthly_gross_revenue_per_reactivated_account"]
    m = a["contribution_margin"]
    outreach = a["outreach_cost_per_target"]
    activation = a["activation_cost_per_reactivation"]
    burden = n * outreach + activation * activation_factor
    thresholds = {
        "minimum_monthly_gross_revenue": burden / ((1 - low) * m * paid_factor)
        if (1 - low) * m * paid_factor > 0
        else None,
        "minimum_contribution_margin": burden / (r * (1 - low) * paid_factor)
        if r * (1 - low) * paid_factor > 0
        else None,
        "maximum_outreach_cost_per_target": (
            r * (1 - low) * m * paid_factor - activation * activation_factor
        )
        / n,
        "maximum_activation_cost": (r * (1 - low) * m * paid_factor - n * outreach)
        / activation_factor
        if activation_factor > 0
        else None,
    }
    rows = [
        {
            "metric": key,
            "commercial_tier": "low_5pct",
            "threshold": value,
            "status": "feasible"
            if value is not None
            and value >= 0
            and (key != "minimum_contribution_margin" or value <= 1)
            else "no_feasible_solution",
            "search_interval": "closed form",
            "baseline_or_target_npv": 0.0,
            "provenance": PROVENANCE,
        }
        for key, value in thresholds.items()
    ]
    target = _expected_npv(hazards, a, low)
    for name in ("medium_15pct", "high_30pct"):
        rate = a["commercial_discount_tiers"][name]
        lo, hi = 1.0, 100.0
        if _expected_npv(hazards * hi, a, rate) < target:
            value, status = None, "no_solution_within_interval"
        else:
            for _ in range(80):
                mid = (lo + hi) / 2
                if _expected_npv(hazards * mid, a, rate) >= target:
                    hi = mid
                else:
                    lo = mid
            value, status = hi, "hypothetical_hazard_multiplier"
        rows.append(
            {
                "metric": "discount_response_hazard_multiplier",
                "commercial_tier": name,
                "threshold": value,
                "status": status,
                "search_interval": "[1,100]",
                "baseline_or_target_npv": target,
                "provenance": PROVENANCE,
            }
        )
    return pd.DataFrame(rows)


def _phase4_contract(
    a: dict, phase2: dict, local_path: str, local_hash: str, row_count: int, account_count: int
) -> dict:
    return {
        "version": "phase3-to-phase4-v1",
        "source_sha256": EXPECTED_SHA256,
        "phase2_assumption_fingerprint_sha256": phase2["assumption_fingerprint_sha256"],
        "phase3_financial_assumption_fingerprint_sha256": a["fingerprint_sha256"],
        "primary_cohort": (
            "reported_2y_scenario_cohort (provisional; fiscal eligibility unconfirmed)"
        ),
        "local_account_input": {
            "path": local_path,
            "sha256": local_hash,
            "classification": "CONFIDENTIAL_LOCAL_ONLY",
            "grain": ["account_id", "reactivation_scenario", "commercial_discount_tier"],
            "expected_rows": row_count,
            "unique_accounts": account_count,
            "schema": {
                "account_id": "string",
                "root_account_id": "string",
                "root_group_identifier": "string",
                "scenario_cohort_status": "string",
                "analysis_as_of_date": "YYYY-MM-DD",
                "reactivation_scenario": "enum",
                "commercial_discount_tier": "enum",
                "commercial_discount_rate": "float [0,1]",
                "account_hazard_per_month": "float >=0",
                "expected_reactivation_probability": "float [0,1]",
                "expected_billed_account_probability": "float [0,1]",
                "expected_pv_gross_revenue": "float >=0",
                "expected_pv_gross_contribution": "float >=0",
                "expected_pv_contribution": "float >=0",
                "expected_pv_activation_cost": "float >=0",
                "allocated_outreach_cost": "float >=0",
                "expected_account_npv": "finite float",
                "health_unknown": "bool",
                "partner_unknown": "bool",
                "tickets_missing": "bool",
                "ticket_sentinel": "bool",
                "has_manual_review_exceptions": "bool",
                "activation_discount_factor_integral": "float [0,1]",
                "paid_month_pv_factor": "float >=0",
                "fiscal_eligibility_confirmed": "bool false",
                "phase2_probability_provenance": "string",
                "financial_provenance": "string",
                "financial_assumption_version": "string",
                "financial_assumption_fingerprint_sha256": "SHA-256",
            },
            "null_policy": (
                "No null keys or economic values; source missingness represented by explicit flags"
            ),
        },
        "permitted_aggregate_outputs": [
            "financial_scenario_matrix.csv",
            "monte_carlo_npv_summary.csv",
            "financial_sensitivity.csv",
            "discount_break_even.csv",
        ],
        "scenarios": list(SCENARIOS),
        "commercial_discount_tiers": a["commercial_discount_tiers"],
        "forecast_horizon_months": a["horizon_months"],
        "financial_horizon_months": a["horizon_months"],
        "currency": a["currency"],
        "valuation_origin": a["valuation_origin"],
        "continuous_month_definition": a["continuous_month_definition"],
        "revenue_recognition_rule": a["revenue_recognition_rule"],
        "activation_cost_timing": a["activation_cost_timing"],
        "outreach_cost_timing": a["outreach_cost_timing"],
        "provenance": PROVENANCE,
        "reporting_label": LABEL,
        "reconciliation": (
            "Scale-aware absolute-plus-relative tolerance capped at $0.001 per scenario cell; "
            "sum local expected components and account NPV to analytic portfolio values"
        ),
        "prohibited_interpretations": [
            "confirmed fiscal-year eligibility",
            "contact authorization from missing ownership",
            "verified healthy status from unknown health",
            "validated customer propensity",
            "verified profitability",
            "historical spend as ARR",
            "synthetic Cox as customer evidence",
            "causally incremental campaign uplift",
            "positive NPV is not contact authorization",
        ],
        "phase4_requirement": (
            "Define review and blocked states for unresolved eligibility, ownership, "
            "health and quality before routing"
        ),
    }


def run_pipeline(repo_root: str | Path, output_dir: str | Path | None = None) -> dict:
    root = Path(repo_root).resolve()
    phase2, a, detail, base = _inputs(root)
    out = Path(output_dir).resolve() if output_dir is not None else root / "outputs/phase3"
    out.mkdir(parents=True, exist_ok=True)
    local = out / "local_only"
    local.mkdir(exist_ok=True)
    write_json(out / "financial_assumptions.json", a)
    n = a["simulations_per_cell"]
    generator = np.random.Generator(np.random.PCG64(a["seed"]))
    uniforms = generator.random((n, len(base)))
    uniforms = np.clip(uniforms, np.nextafter(0.0, 1.0), np.nextafter(1.0, 0.0))
    if np.unique(uniforms, axis=0).shape[0] != n:
        raise ValueError("Duplicate replication draw vector")
    runs, summaries, months, signals, matrix = [], [], [], [], []
    prior_times = None
    for scenario in SCENARIOS:
        hazards = _scenario_hazards(detail, base, scenario)
        times = event_times(uniforms, hazards)
        if prior_times is not None and not np.all(times <= prior_times):
            raise ValueError("Shared-draw scenario event times are not nested")
        prior_times = times
        for tier in ("low_5pct", "medium_15pct", "high_30pct"):
            rate = a["commercial_discount_tiers"][tier]
            expected = account_expectation(hazards, a, rate)
            analytic = float(expected.expected_account_npv.sum())
            run, monthly = pathwise(times, a, rate)
            run.insert(0, "simulation_id", np.arange(1, n + 1))
            run.insert(1, "reactivation_scenario", scenario)
            run.insert(2, "commercial_discount_tier", tier)
            run.insert(3, "commercial_discount_rate", rate)
            if not np.allclose(
                run.npv,
                run.pv_contribution - run.pv_activation_cost - run.outreach_cost,
                rtol=0,
                atol=1e-7,
            ):
                raise ValueError("Pathwise financial bridge failed")
            if abs(monthly.mean_pv_net_cashflow.sum() - run.npv.mean()) > 1e-7:
                raise ValueError("Monthly cash flow NPV mismatch")
            result = summarize(
                run.drop(
                    columns=[
                        "simulation_id",
                        "reactivation_scenario",
                        "commercial_discount_tier",
                        "commercial_discount_rate",
                    ]
                ),
                analytic,
            )
            result.update(
                {
                    "reactivation_scenario": scenario,
                    "commercial_discount_tier": tier,
                    "commercial_discount_rate": rate,
                    "modeled_accounts": len(base),
                    "reporting_label": LABEL,
                    "provenance": PROVENANCE,
                    "analytic_expected_pv_gross_revenue": float(
                        expected.expected_pv_gross_revenue.sum()
                    ),
                    "analytic_expected_pv_gross_contribution": float(
                        expected.expected_pv_gross_contribution.sum()
                    ),
                    "analytic_expected_pv_contribution": float(
                        expected.expected_pv_contribution.sum()
                    ),
                    "analytic_expected_pv_activation_cost": float(
                        expected.expected_pv_activation_cost.sum()
                    ),
                    "analytic_outreach_cost": float(expected.allocated_outreach_cost.sum()),
                }
            )
            if abs(result["standardized_discrepancy"]) > Z_LIMIT:
                raise ValueError(f"Monte Carlo oracle discrepancy: {scenario}/{tier}")
            monthly.insert(0, "reactivation_scenario", scenario)
            monthly.insert(1, "commercial_discount_tier", tier)
            monthly.insert(2, "commercial_discount_rate", rate)
            monthly["modeled_accounts"] = len(base)
            months.append(monthly)
            runs.append(run)
            summaries.append(result)
            matrix.append(
                {
                    "reactivation_scenario": scenario,
                    "commercial_discount_tier": tier,
                    "commercial_discount_rate": rate,
                    "simulations": n,
                    "modeled_accounts": len(base),
                    "analytical_expected_npv": analytic,
                    "mean_simulated_npv": result["mean_npv"],
                    "provenance": PROVENANCE,
                }
            )
            signal = pd.concat(
                [
                    base[
                        [
                            "account_id",
                            "root_account_id",
                            "scenario_cohort_status",
                            "health_unknown",
                            "partner_unknown",
                            "tickets_missing",
                            "ticket_sentinel",
                            "has_manual_review_exceptions",
                        ]
                    ].reset_index(drop=True),
                    expected.reset_index(drop=True),
                ],
                axis=1,
            )
            signal["root_group_identifier"] = signal.root_account_id
            signal["analysis_as_of_date"] = a["valuation_origin"]
            signal["reactivation_scenario"] = scenario
            signal["commercial_discount_tier"] = tier
            signal["commercial_discount_rate"] = rate
            signal["account_hazard_per_month"] = hazards
            signal["fiscal_eligibility_confirmed"] = False
            signal["phase2_probability_provenance"] = PROVENANCE
            signal["financial_provenance"] = PROVENANCE
            signal["financial_assumption_version"] = a["version"]
            signal["financial_assumption_fingerprint_sha256"] = a["fingerprint_sha256"]
            if abs(signal.expected_account_npv.sum() - analytic) > financial_tolerance(analytic):
                raise ValueError("Account NPV reconciliation failed")
            signals.append(signal)
    runs = pd.concat(runs, ignore_index=True)
    summaries = pd.DataFrame(summaries)
    months = pd.concat(months, ignore_index=True)
    signals = pd.concat(signals, ignore_index=True)
    if (
        len(runs) != n * len(SCENARIOS) * len(a["commercial_discount_tiers"])
        or len(signals) != len(base) * len(SCENARIOS) * len(a["commercial_discount_tiers"])
        or runs.duplicated(
            ["simulation_id", "reactivation_scenario", "commercial_discount_tier"]
        ).any()
        or signals.duplicated(
            ["account_id", "reactivation_scenario", "commercial_discount_tier"]
        ).any()
    ):
        raise ValueError("Phase 3 output grain mismatch")
    write_csv(out / "financial_scenario_matrix.csv", pd.DataFrame(matrix))
    write_csv(out / "monte_carlo_run_results.csv", runs)
    write_csv(out / "monte_carlo_npv_summary.csv", summaries)
    write_csv(out / "monthly_cashflow_summary.csv", months)
    base_h = _scenario_hazards(detail, base, "base")
    write_csv(out / "financial_sensitivity.csv", financial_sensitivity(base_h, a))
    write_csv(out / "discount_break_even.csv", break_even(base_h, a))
    write_csv(local / "account_economic_signals.csv", signals)
    reconciliation = {
        "version": "phase3-financial-reconciliation-v1",
        "z_limit": Z_LIMIT,
        "max_absolute_standardized_discrepancy": float(
            summaries.standardized_discrepancy.abs().max()
        ),
        "cells": summaries[
            [
                "reactivation_scenario",
                "commercial_discount_tier",
                "analytic_expected_npv",
                "mean_npv",
                "mc_standard_error",
                "standardized_discrepancy",
            ]
        ].to_dict(orient="records"),
        "account_reconciliation_tolerance": "min(0.001, 1e-8 + 2e-12 * max(1, abs(scale))) USD",
        "monthly_cashflow_tolerance_usd": 1e-7,
    }
    write_json(out / "financial_reconciliation.json", reconciliation)
    local_file = local / "account_economic_signals.csv"
    local_path = (
        local_file.relative_to(root).as_posix()
        if local_file.is_relative_to(root)
        else local_file.name
    )
    phase4 = _phase4_contract(a, phase2, local_path, sha256(local_file), len(signals), len(base))
    write_json(out / "phase4_input_contract.json", phase4)
    validate_phase4_handoff(out)
    metrics = {
        "version": "phase3-metrics-v1",
        "source_sha256": EXPECTED_SHA256,
        "phase2_probability_sha256": phase2["probability_artifact_sha256"],
        "phase2_assumption_fingerprint_sha256": phase2["assumption_fingerprint_sha256"],
        "financial_assumption_fingerprint_sha256": a["fingerprint_sha256"],
        "modeled_accounts": len(base),
        "scenario_cells": len(summaries),
        "replications_per_cell": n,
        "run_records": len(runs),
        "local_account_signal_rows": len(signals),
        "reporting_label": LABEL,
        "random_generator": "NumPy PCG64",
        "seed": a["seed"],
        "common_random_numbers": True,
        "analytic_reconciliation_z_limit": Z_LIMIT,
    }
    write_json(out / "metrics.json", metrics)
    files = sorted(p for p in out.iterdir() if p.is_file() and p.name != "manifest.json")
    manifest = {
        "version": "phase3-artifact-manifest-v1",
        "source_sha256": EXPECTED_SHA256,
        "phase2_probability_sha256": phase2["probability_artifact_sha256"],
        "financial_assumption_fingerprint_sha256": a["fingerprint_sha256"],
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "files": [
            {
                "path": str(p.relative_to(root)).replace("\\", "/")
                if p.is_relative_to(root)
                else p.name,
                "sha256": sha256(p),
                "provenance": PROVENANCE,
                "classification": "AGGREGATE",
            }
            for p in files
        ],
        "local_only": {
            "path": local_path,
            "sha256": sha256(local / "account_economic_signals.csv"),
            "classification": "CONFIDENTIAL_LOCAL_ONLY",
        },
    }
    write_json(out / "manifest.json", manifest)
    validate_phase3_artifacts(root, output_dir=out, mode="handoff")
    return metrics


def validate_phase4_handoff(out: Path) -> None:
    """Validate the confidential handoff against its contract and portfolio oracle."""
    contract = json.loads((out / "phase4_input_contract.json").read_text(encoding="utf-8"))
    spec = contract["local_account_input"]
    path = out / "local_only/account_economic_signals.csv"
    if sha256(path) != spec["sha256"]:
        raise ValueError("Phase 4 local account hash mismatch")
    frame = pd.read_csv(path, dtype={"account_id": str, "root_account_id": str})
    summary = pd.read_csv(out / "monte_carlo_npv_summary.csv")
    if (
        len(frame) != spec["expected_rows"]
        or frame.account_id.nunique() != spec["unique_accounts"]
        or frame.duplicated(spec["grain"]).any()
        or set(frame) != set(spec["schema"])
        or frame.isna().any().any()
    ):
        raise ValueError("Phase 4 local account schema or grain mismatch")
    if not frame.root_account_id.eq(frame.root_group_identifier).all():
        raise ValueError("Phase 4 root group mismatch")
    if (
        contract["version"] != "phase3-to-phase4-v1"
        or contract["source_sha256"] != EXPECTED_SHA256
        or not frame.reactivation_scenario.isin(contract["scenarios"]).all()
        or not frame.commercial_discount_tier.isin(contract["commercial_discount_tiers"]).all()
        or not np.allclose(
            frame.commercial_discount_rate,
            frame.commercial_discount_tier.map(contract["commercial_discount_tiers"]),
            rtol=0,
            atol=1e-15,
        )
        or not frame.analysis_as_of_date.eq(contract["valuation_origin"]).all()
        or not frame.financial_assumption_fingerprint_sha256.eq(
            contract["phase3_financial_assumption_fingerprint_sha256"]
        ).all()
    ):
        raise ValueError("Phase 4 handoff contract identity mismatch")
    for flag in (
        "health_unknown",
        "partner_unknown",
        "tickets_missing",
        "ticket_sentinel",
        "has_manual_review_exceptions",
        "fiscal_eligibility_confirmed",
    ):
        if not pd.api.types.is_bool_dtype(frame[flag]):
            raise ValueError(f"Phase 4 flag type mismatch: {flag}")
    if (
        frame.fiscal_eligibility_confirmed.any()
        or not frame.scenario_cohort_status.eq("primary_reported_2y").all()
        or not frame.phase2_probability_provenance.eq(PROVENANCE).all()
        or not frame.financial_provenance.eq(PROVENANCE).all()
    ):
        raise ValueError("Phase 4 provenance or eligibility mismatch")
    bounded = [
        "expected_reactivation_probability",
        "expected_billed_account_probability",
        "commercial_discount_rate",
        "activation_discount_factor_integral",
    ]
    positive = [
        "expected_pv_gross_revenue",
        "expected_pv_gross_contribution",
        "expected_pv_contribution",
        "expected_pv_activation_cost",
        "allocated_outreach_cost",
        "paid_month_pv_factor",
        "account_hazard_per_month",
    ]
    if (
        not np.isfinite(frame[bounded + positive + ["expected_account_npv"]]).all().all()
        or not frame[bounded].ge(0).all().all()
        or not frame[bounded].le(1).all().all()
        or not frame[positive].ge(0).all().all()
    ):
        raise ValueError("Phase 4 economic range mismatch")
    bridged = (
        frame.expected_pv_contribution
        - frame.expected_pv_activation_cost
        - frame.allocated_outreach_cost
    )
    account_scale = (
        frame.expected_pv_contribution.abs()
        + frame.expected_pv_activation_cost.abs()
        + frame.allocated_outreach_cost.abs()
    )
    if not (
        np.abs(frame.expected_account_npv - bridged)
        <= financial_tolerance(account_scale.to_numpy())
    ).all():
        raise ValueError("Phase 4 account economic bridge mismatch")
    for row in summary.itertuples(index=False):
        subset = frame.loc[
            (frame.reactivation_scenario == row.reactivation_scenario)
            & (frame.commercial_discount_tier == row.commercial_discount_tier)
        ]
        if len(subset) != spec["unique_accounts"]:
            raise ValueError("Phase 4 scenario cell count mismatch")
        for column, target in (
            ("expected_account_npv", row.analytic_expected_npv),
            ("expected_pv_gross_revenue", row.analytic_expected_pv_gross_revenue),
            ("expected_pv_gross_contribution", row.analytic_expected_pv_gross_contribution),
            ("expected_pv_contribution", row.analytic_expected_pv_contribution),
            ("expected_pv_activation_cost", row.analytic_expected_pv_activation_cost),
            ("allocated_outreach_cost", row.analytic_outreach_cost),
        ):
            if abs(subset[column].sum() - target) > financial_tolerance(target):
                raise ValueError(f"Phase 4 portfolio reconciliation mismatch: {column}")


def validate_phase3_artifacts(
    repo_root: str | Path,
    *,
    output_dir: str | Path | None = None,
    mode: str = "handoff",
) -> dict:
    """Check artifact freshness and recompute the Phase 4 financial input oracle.

    Hashes establish internal consistency, not authenticity if an attacker can
    rewrite both an artifact and its manifest. The source SHA and frozen Phase 2
    contract provide additional anchors; real financial assumptions remain
    analyst-selected inputs.
    """
    if mode not in {"handoff", "complete"}:
        raise ValueError("Unknown Phase 3 validation mode")
    root = Path(repo_root).resolve()
    out = Path(output_dir).resolve() if output_dir is not None else root / "outputs/phase3"
    if not out.is_relative_to(root):
        raise ValueError("Phase 3 output must reside inside repository")
    phase2, a, detail, base = _inputs(root)
    manifest_path = out / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ValueError("Missing or malformed Phase 3 manifest") from exc
    expected_manifest_keys = {
        "version",
        "source_sha256",
        "phase2_probability_sha256",
        "financial_assumption_fingerprint_sha256",
        "python_version",
        "numpy_version",
        "pandas_version",
        "files",
        "local_only",
    }
    if not expected_manifest_keys.issubset(manifest) or set(manifest) - expected_manifest_keys - {
        "notebook",
        "figures",
    }:
        raise ValueError("Unexpected Phase 3 manifest structure")

    def verify_entry(entry: dict, expected: Path) -> None:
        if (
            not isinstance(entry, dict)
            or entry.get("path") != expected.relative_to(root).as_posix()
            or not isinstance(entry.get("sha256"), str)
        ):
            raise ValueError(f"Phase 3 manifest path or hash field mismatch: {expected.name}")
        if not expected.is_file() or sha256(expected) != entry["sha256"]:
            raise ValueError(f"Phase 3 artifact hash mismatch or missing file: {expected.name}")

    if (
        manifest.get("version") != "phase3-artifact-manifest-v1"
        or manifest.get("source_sha256") != EXPECTED_SHA256
        or manifest.get("phase2_probability_sha256") != phase2["probability_artifact_sha256"]
        or manifest.get("financial_assumption_fingerprint_sha256") != fingerprint(a)
    ):
        raise ValueError("Phase 3 manifest identity mismatch")
    entries = manifest.get("files")
    if (
        not isinstance(entries, list)
        or len(entries) != len(AGGREGATE_ARTIFACTS)
        or {Path(e.get("path", "")).name for e in entries if isinstance(e, dict)}
        != AGGREGATE_ARTIFACTS
    ):
        raise ValueError("Phase 3 aggregate manifest inventory mismatch")
    for entry in entries:
        verify_entry(entry, out / Path(entry["path"]).name)
    local_file = out / "local_only/account_economic_signals.csv"
    verify_entry(manifest.get("local_only"), local_file)
    notebook_entry = manifest.get("notebook")
    figure_entries = manifest.get("figures")
    if mode == "complete" and (notebook_entry is None or figure_entries is None):
        raise ValueError("Phase 3 notebook or figures missing from manifest")
    if notebook_entry is not None:
        verify_entry(notebook_entry, root / "notebooks/03_monte_carlo_npv.ipynb")
    if figure_entries is not None:
        if (
            not isinstance(figure_entries, list)
            or len(figure_entries) != len(FIGURE_ARTIFACTS)
            or {Path(e.get("path", "")).name for e in figure_entries if isinstance(e, dict)}
            != FIGURE_ARTIFACTS
        ):
            raise ValueError("Phase 3 figure inventory mismatch")
        for entry in figure_entries:
            verify_entry(entry, out / "figures" / Path(entry["path"]).name)

    exported = json.loads((out / "financial_assumptions.json").read_text(encoding="utf-8"))
    handoff = json.loads((out / "phase4_input_contract.json").read_text(encoding="utf-8"))
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    if (
        exported != a
        or exported.get("fingerprint_sha256") != fingerprint(a)
        or handoff.get("phase3_financial_assumption_fingerprint_sha256") != fingerprint(a)
        or handoff.get("phase2_assumption_fingerprint_sha256")
        != phase2["assumption_fingerprint_sha256"]
        or handoff.get("source_sha256") != EXPECTED_SHA256
        or handoff.get("local_account_input", {}).get("sha256") != manifest["local_only"]["sha256"]
        or handoff.get("local_account_input", {}).get("path")
        != local_file.relative_to(root).as_posix()
        or handoff.get("financial_horizon_months") != a["horizon_months"]
        or handoff.get("commercial_discount_tiers") != a["commercial_discount_tiers"]
        or metrics.get("financial_assumption_fingerprint_sha256") != fingerprint(a)
        or metrics.get("phase2_assumption_fingerprint_sha256")
        != phase2["assumption_fingerprint_sha256"]
        or metrics.get("phase2_probability_sha256") != phase2["probability_artifact_sha256"]
    ):
        raise ValueError("Phase 3 financial assumptions or handoff are stale")
    validate_phase4_handoff(out)

    signal = pd.read_csv(local_file, dtype={"account_id": str, "root_account_id": str})
    summary = pd.read_csv(out / "monte_carlo_npv_summary.csv")
    runs = pd.read_csv(out / "monte_carlo_run_results.csv")
    monthly = pd.read_csv(out / "monthly_cashflow_summary.csv")
    expected_cells = len(SCENARIOS) * len(a["commercial_discount_tiers"])
    if (
        len(summary) != expected_cells
        or summary.duplicated(["reactivation_scenario", "commercial_discount_tier"]).any()
        or len(signal) != len(base) * expected_cells
        or len(runs) != a["simulations_per_cell"] * expected_cells
        or runs.duplicated(
            ["simulation_id", "reactivation_scenario", "commercial_discount_tier"]
        ).any()
    ):
        raise ValueError("Phase 3 analytical scenario grain mismatch")
    checked = 0
    for scenario in SCENARIOS:
        hazards = _scenario_hazards(detail, base, scenario)
        for tier, rate in a["commercial_discount_tiers"].items():
            oracle = account_expectation(hazards, a, rate)
            subset = signal.loc[
                (signal.reactivation_scenario == scenario)
                & (signal.commercial_discount_tier == tier)
            ]
            subset = subset.sort_values(["account_id", "root_account_id"]).reset_index(drop=True)
            if (
                not subset.account_id.equals(base.account_id)
                or not subset.root_account_id.equals(base.root_account_id)
                or not np.allclose(subset.account_hazard_per_month, hazards, rtol=0, atol=1e-14)
            ):
                raise ValueError("Phase 3 account identity or hazard mismatch")
            for column in (
                "expected_reactivation_probability",
                "expected_billed_account_probability",
                "expected_pv_gross_revenue",
                "expected_pv_gross_contribution",
                "expected_pv_contribution",
                "expected_pv_activation_cost",
                "allocated_outreach_cost",
                "expected_account_npv",
            ):
                expected = oracle[column].to_numpy()
                actual = subset[column].to_numpy()
                tolerance = (
                    np.full(len(expected), 1e-12)
                    if "probability" in column
                    else financial_tolerance(expected)
                )
                if not (np.abs(actual - expected) <= tolerance).all():
                    raise ValueError(f"Phase 3 independent account oracle mismatch: {column}")
            row = summary.loc[
                (summary.reactivation_scenario == scenario)
                & (summary.commercial_discount_tier == tier)
            ]
            if len(row) != 1 or abs(
                row.analytic_expected_npv.iloc[0] - oracle.expected_account_npv.sum()
            ) > financial_tolerance(oracle.expected_account_npv.sum()):
                raise ValueError("Phase 3 independent portfolio oracle mismatch")
            run_subset = runs.loc[
                (runs.reactivation_scenario == scenario) & (runs.commercial_discount_tier == tier)
            ]
            if len(run_subset) != a["simulations_per_cell"] or set(run_subset.simulation_id) != set(
                range(1, a["simulations_per_cell"] + 1)
            ):
                raise ValueError("Phase 3 simulation replication grain mismatch")
            recomputed = summarize(
                run_subset.drop(
                    columns=[
                        "simulation_id",
                        "reactivation_scenario",
                        "commercial_discount_tier",
                        "commercial_discount_rate",
                    ]
                ),
                float(oracle.expected_account_npv.sum()),
            )
            for field, value in recomputed.items():
                if field not in row or abs(row[field].iloc[0] - value) > financial_tolerance(value):
                    raise ValueError(f"Phase 3 run summary mismatch: {field}")
            monthly_subset = monthly.loc[
                (monthly.reactivation_scenario == scenario)
                & (monthly.commercial_discount_tier == tier)
            ]
            if set(monthly_subset.month) != set(range(a["horizon_months"] + 1)) or abs(
                monthly_subset.mean_pv_net_cashflow.sum() - run_subset.npv.mean()
            ) > financial_tolerance(run_subset.npv.mean()):
                raise ValueError("Phase 3 monthly cash flow mismatch")
            checked += 1
    return {
        "mode": mode,
        "verified_cells": checked,
        "verified_manifest_entries": len(entries)
        + 1
        + int(notebook_entry is not None)
        + (len(figure_entries) if figure_entries is not None else 0),
        "financial_assumption_fingerprint_sha256": fingerprint(a),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase 3 illustrative financial Monte Carlo")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(run_pipeline(args.repo_root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
