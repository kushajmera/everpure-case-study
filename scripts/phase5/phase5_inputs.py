"""Validated, aggregate-only inputs for the Phase 5 executive submission.

Every number placed in the deck, appendix, README and evidence index comes from
``load_validated_facts``. It re-runs the frozen upstream validators, pins the Phase 5
handoff contract byte-for-byte, hash-checks every aggregate it reads against the
upstream manifests and recomputes the root concentration and both adverse stress
vectors with the frozen financial code. Nothing here writes to the repository.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from everpure_case.financial_model import account_expectation  # noqa: E402
from everpure_case.gtm_policy import (  # noqa: E402
    REQUIRED_DISCLOSURES_SHA256,
    canonical_hash,
    load_policy,
)
from everpure_case.ingestion import read_source  # noqa: E402
from everpure_case.phase4_pipeline import SAFE_FILES, validate_phase4_artifacts  # noqa: E402
from everpure_case.reactivation_scenarios import assumption_fingerprint  # noqa: E402
from everpure_case.source_integrity import (  # noqa: E402
    EXPECTED_SHA256,
    verify_authoritative_source,
)

FROZEN = {
    "branch": "main",
    "phase4_head": "38b1f43e005d05e738802ab0b15eab51791eb325",
    "commits": {
        "phase1": "1f0fa172d648fb07ffd7e2b7eddbc30470af750e",
        "phase2": "1d8b136d14fb6cd3171326815a7a2362ac56894d",
        "phase3": "e94f17464d02b51c761d594c47c1d88433a22a4f",
        "phase3_integrity_fix": "3459169787f1ffd78024ce8ee85571d7ef4ac658",
        "phase4": "38b1f43e005d05e738802ab0b15eab51791eb325",
    },
    "source_sha256": "6863ea0014f050355bf9e0c5166e2284edfe8521ea3d87a2a2fa168177a229bc",
    "phase2_assumption_fingerprint": (
        "6195ba2e90c95976ed91b7bdd42509341fd22e71e6b2bb5aed2e5d2a6d346ee7"
    ),
    "phase3_financial_fingerprint": (
        "b953c02d3fdcfacc62d9e6755889040e9f8bd12db7c830a88c79f5c991267e70"
    ),
    "phase4_policy_fingerprint": (
        "1998cc4a68c88160f01d89ca0abfe7c2ae955d912181b872556c149e5201af3c"
    ),
    "phase4_manifest_sha256": "6e8f7068a21db325e6f567a469fe3e23d0c0eac7e917c96851e531e9255d515d",
    "phase5_contract_sha256": "89bfe72319e31112fa64b837b741e664278ab919d45c8f6ad3614adc2613398a",
    "contract_version": "phase4-to-phase5-v2",
    "classification": "AGGREGATE_ONLY",
}
SCENARIOS = ("conservative", "base", "optimistic")
TIERS = ("low_5pct", "medium_15pct", "high_30pct")
STRESS_TOLERANCE_USD = 1e-6


class Phase5InputError(ValueError):
    """An upstream artifact is stale, altered or inconsistent with the frozen baseline."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Phase5InputError(message)


def _manifest_hashes(root: Path) -> dict[str, str]:
    """Map repository-relative paths to the SHA-256 recorded by the Phase 2-3 manifests."""
    hashes: dict[str, str] = {}
    p2 = json.loads((root / "outputs/phase2/manifest.json").read_text(encoding="utf-8"))
    for item in p2["files"]:
        hashes[f"outputs/phase2/{item['name']}"] = item["sha256"]
    p3 = json.loads((root / "outputs/phase3/manifest.json").read_text(encoding="utf-8"))
    for item in p3["files"] + p3.get("figures", []):
        hashes[item["path"]] = item["sha256"]
    return hashes


def _read_verified(root: Path, relative: str, hashes: dict[str, str]) -> Path:
    path = root / relative
    _require(relative in hashes, f"{relative} is not listed in an upstream manifest")
    _require(sha256(path) == hashes[relative], f"{relative} hash differs from its manifest")
    return path


def _contract(root: Path) -> tuple[dict, dict]:
    out = root / "outputs/phase4"
    contract_path = out / "phase5_input_contract.json"
    manifest_path = out / "manifest.json"
    _require(
        sha256(contract_path) == FROZEN["phase5_contract_sha256"],
        "Phase 5 input contract bytes differ from the frozen handoff",
    )
    _require(
        sha256(manifest_path) == FROZEN["phase4_manifest_sha256"],
        "Phase 4 manifest bytes differ from the frozen handoff",
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _require(contract["version"] == FROZEN["contract_version"], "Unsupported contract version")
    _require(contract["classification"] == FROZEN["classification"], "Contract not aggregate-only")
    _require(contract["source_sha256"] == FROZEN["source_sha256"], "Source fingerprint mismatch")
    _require(
        contract["phase2_assumption_fingerprint_sha256"] == FROZEN["phase2_assumption_fingerprint"],
        "Phase 2 assumption fingerprint mismatch",
    )
    _require(
        contract["phase3_financial_assumption_fingerprint_sha256"]
        == FROZEN["phase3_financial_fingerprint"],
        "Phase 3 financial fingerprint mismatch",
    )
    _require(
        contract["phase4_policy_fingerprint_sha256"] == FROZEN["phase4_policy_fingerprint"],
        "Phase 4 policy fingerprint mismatch",
    )
    _require(
        contract["cohort_denominators"]
        == {"source_accounts": 2000, "modeled_accounts": 1144, "modeled_roots": 295},
        "Cohort denominators changed",
    )
    _require(
        (contract["reference_scenario"], contract["reference_discount_tier"])
        == ("base", "medium_15pct"),
        "Reference financial cell changed",
    )
    _require(contract["financial_horizon_months"] == 12, "Financial horizon changed")
    _require(
        set(contract["permitted_aggregate_files"]) == set(SAFE_FILES), "Permitted files differ"
    )
    for name, digest in contract["permitted_aggregate_files"].items():
        _require(sha256(out / name) == digest, f"Aggregate hash mismatch: {name}")
        _require(manifest["safe"][name] == digest, f"Manifest/contract disagreement: {name}")
        if name.endswith(".csv"):
            header = pd.read_csv(out / name, nrows=0).columns.tolist()
            _require(
                header == contract["aggregate_schemas"][name]["columns"],
                f"Aggregate schema mismatch: {name}",
            )
    policy = load_policy(root)
    _require(canonical_hash(policy) == FROZEN["phase4_policy_fingerprint"], "Policy drifted")
    _require(
        contract["executive_disclosures"] == policy["required_executive_disclosures"]
        and canonical_hash(contract["executive_disclosures"]) == REQUIRED_DISCLOSURES_SHA256,
        "Required executive disclosures were altered",
    )
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    _require(sorted(metrics) == contract["metrics_schema"]["keys"], "Metrics schema changed")
    return contract, metrics


def _csv(root: Path, relative: str) -> pd.DataFrame:
    return pd.read_csv(root / relative, float_precision="round_trip")


def _counts(frame: pd.DataFrame, key: str, value: str = "account_count") -> dict[str, int]:
    return {str(k): int(v) for k, v in zip(frame[key], frame[value], strict=True)}


def _stress_vectors(root: Path, contract: dict, financial_assumptions: dict) -> dict:
    """Recompute both documented adverse stress vectors from frozen account hazards."""
    local = root / "outputs/phase3/local_only/account_economic_signals.csv"
    signals = pd.read_csv(local, float_precision="round_trip", dtype={"account_id": str})
    base = signals.loc[
        signals.reactivation_scenario.eq("base")
        & signals.commercial_discount_tier.eq("medium_15pct")
    ].sort_values("account_id")
    _require(len(base) == 1144 and base.account_id.is_unique, "Unexpected reference grain")
    hazards = base.account_hazard_per_month.to_numpy(dtype=float)

    def npv(overrides: dict, hazard_multiplier: float, cap: int | None) -> float:
        a = {**financial_assumptions, **overrides}
        frame = account_expectation(hazards * hazard_multiplier, a, 0.15, retention_paid_months=cap)
        return float(frame.expected_account_npv.sum())

    reference = npv({}, 1.0, None)
    committed = npv(
        {
            "monthly_gross_revenue_per_reactivated_account": 750.0,
            "contribution_margin": 0.45,
            "outreach_cost_per_target": 150.0,
            "activation_cost_per_reactivation": 300.0,
            "annual_effective_financial_discount_rate": 0.24,
        },
        1.0,
        3,
    )
    alternative = npv(
        {
            "monthly_gross_revenue_per_reactivated_account": 750.0,
            "contribution_margin": 0.60,
            "outreach_cost_per_target": 150.0,
            "activation_cost_per_reactivation": 200.0,
            "annual_effective_financial_discount_rate": 0.12,
        },
        0.5,
        3,
    )
    disclosed = {}
    for key in ("committed_adverse_stress", "alternative_compounded_stress"):
        match = re.search(r"NPV -\$([0-9,]+\.[0-9]+)", contract["executive_disclosures"][key])
        _require(match is not None, f"Disclosure {key} lacks an NPV")
        disclosed[key] = -float(match.group(1).replace(",", ""))
    _require(
        abs(reference - 201501.65868186974) < STRESS_TOLERANCE_USD,
        "Reference NPV recomputation mismatch",
    )
    _require(
        abs(committed - disclosed["committed_adverse_stress"]) < STRESS_TOLERANCE_USD,
        "Committed stress recomputation mismatch",
    )
    _require(
        abs(alternative - disclosed["alternative_compounded_stress"]) < STRESS_TOLERANCE_USD,
        "Alternative stress recomputation mismatch",
    )
    roots = base.groupby("root_account_id").agg(
        accounts=("account_id", "size"), npv=("expected_account_npv", "sum")
    )
    multi = roots.loc[roots.accounts.gt(1)]
    return {
        "reference_recomputed_usd": reference,
        "committed_adverse_npv_usd": committed,
        "alternative_compounded_npv_usd": alternative,
        "committed_disclosed_usd": disclosed["committed_adverse_stress"],
        "alternative_disclosed_usd": disclosed["alternative_compounded_stress"],
        "multi_account_roots": int(len(multi)),
        "modeled_roots": int(len(roots)),
        "multi_account_root_npv_share": float(multi.npv.sum() / roots.npv.sum()),
    }


def load_validated_facts(repo_root: str | Path = ROOT) -> dict:
    """Return every Phase 5 number after full upstream validation; raise on any drift."""
    root = Path(repo_root).resolve()
    source = verify_authoritative_source(root)
    _require(source["source_sha256"] == EXPECTED_SHA256 == FROZEN["source_sha256"], "Source")
    # Read-only semantic re-derivation of every Phase 4 route and aggregate from the source.
    validate_phase4_artifacts(root)
    contract, p4_metrics = _contract(root)
    hashes = _manifest_hashes(root)

    p2_assumptions = json.loads((root / "docs/PHASE_2_ASSUMPTIONS.json").read_text("utf-8"))
    _require(
        assumption_fingerprint(p2_assumptions) == FROZEN["phase2_assumption_fingerprint"],
        "Phase 2 assumption register drifted",
    )
    fin = json.loads((root / "docs/PHASE_3_FINANCIAL_ASSUMPTIONS.json").read_text("utf-8"))
    _require(fin["fingerprint_sha256"] == FROZEN["phase3_financial_fingerprint"], "P3 drifted")

    p1 = json.loads((root / "outputs/phase1/metrics.json").read_text(encoding="utf-8"))
    _require(p1["source_sha256"] == FROZEN["source_sha256"], "Phase 1 metrics source mismatch")
    _require(p1["analysis_as_of_date"] == "2026-10-09", "Phase 1 analysis date changed")
    _require(sum(p1["issue_counts"].values()) == p1["quality_exception_rows"], "Issue counts")
    raw = read_source(root / "data/raw/Case_Study_1_Install_Base_Reactivation.csv")
    health_raw = raw.sfdc_health_score.value_counts().to_dict()

    p2_summary = pd.read_csv(
        _read_verified(root, "outputs/phase2/reactivation_scenario_summary.csv", hashes)
    )
    p2_sens = pd.read_csv(_read_verified(root, "outputs/phase2/scenario_sensitivity.csv", hashes))
    cox = pd.read_csv(_read_verified(root, "outputs/phase2/synthetic_cox_coefficients.csv", hashes))
    diag = json.loads(
        _read_verified(root, "outputs/phase2/synthetic_model_diagnostics.json", hashes).read_text(
            encoding="utf-8"
        )
    )
    matrix = pd.read_csv(
        _read_verified(root, "outputs/phase3/financial_scenario_matrix.csv", hashes),
        float_precision="round_trip",
    )
    mc = pd.read_csv(
        _read_verified(root, "outputs/phase3/monte_carlo_npv_summary.csv", hashes),
        float_precision="round_trip",
    )
    sens = pd.read_csv(
        _read_verified(root, "outputs/phase3/financial_sensitivity.csv", hashes),
        float_precision="round_trip",
    )
    breakeven = pd.read_csv(
        _read_verified(root, "outputs/phase3/discount_break_even.csv", hashes),
        float_precision="round_trip",
    )
    p3_metrics = json.loads(
        _read_verified(root, "outputs/phase3/metrics.json", hashes).read_text(encoding="utf-8")
    )

    out = "outputs/phase4/"
    channels = _csv(root, out + "routing_channel_summary.csv")
    rules = _csv(root, out + "routing_rule_counts.csv")
    priority = _csv(root, out + "commercial_priority_summary.csv")
    evidence = _csv(root, out + "priority_evidence_summary.csv")
    readiness = _csv(root, out + "data_readiness_summary.csv")
    service = _csv(root, out + "service_barrier_summary.csv")
    roots = _csv(root, out + "root_coordination_summary.csv")
    cohort = _csv(root, out + "cohort_reconciliation_summary.csv")
    scen_priority = _csv(root, out + "scenario_priority_sensitivity.csv")

    stress = _stress_vectors(root, contract, fin)

    # ---- assemble facts with cross-artifact reconciliation ----
    cohort_counts = _counts(cohort, "scenario_cohort_status")
    channel_counts = _counts(channels, "planning_disposition")
    _require(channel_counts == p4_metrics["channels"], "Channel aggregate/metrics mismatch")
    _require(sum(channel_counts.values()) == 1144, "Channels do not reconcile to 1,144")
    _require(sum(cohort_counts.values()) == 2000, "Cohort does not reconcile to 2,000")
    priority_counts = _counts(priority, "commercial_priority_tier")
    _require(sum(priority_counts.values()) == 1144, "Priority tiers do not reconcile")
    readiness_counts = _counts(readiness, "measure")
    root_counts = _counts(roots, "measure", "root_count")
    _require(
        root_counts["full_source_known_ownership_conflict_roots"]
        == p4_metrics["full_source_known_ownership_conflict_roots"]
        and root_counts["coordination_required_roots"]
        == p4_metrics["root_coordination_required_roots"],
        "Root aggregate/metrics mismatch",
    )
    _require(
        readiness_counts["root_coordination_required"]
        == p4_metrics["root_coordination_required_accounts"],
        "Coordination account mismatch",
    )
    _require(readiness_counts["execution_authorized"] == 0, "Execution authorization present")
    _require(p4_metrics["authorized_contact_actions"] == 0, "Contact actions present")

    nine: dict[str, dict[str, dict]] = {}
    for row in matrix.itertuples(index=False):
        mrow = mc.loc[
            mc.reactivation_scenario.eq(row.reactivation_scenario)
            & mc.commercial_discount_tier.eq(row.commercial_discount_tier)
        ].iloc[0]
        srow = scen_priority.loc[
            scen_priority.reactivation_scenario.eq(row.reactivation_scenario)
            & scen_priority.commercial_discount_tier.eq(row.commercial_discount_tier)
        ].iloc[0]
        _require(
            math.isclose(row.analytical_expected_npv, mrow.analytic_expected_npv, abs_tol=1e-6)
            and math.isclose(
                row.analytical_expected_npv, srow.illustrative_sum_account_npv_usd, abs_tol=1e-6
            )
            and math.isclose(row.mean_simulated_npv, mrow.mean_npv, abs_tol=1e-6),
            "Nine-cell values disagree across Phase 3 and Phase 4 artifacts",
        )
        nine.setdefault(row.reactivation_scenario, {})[row.commercial_discount_tier] = {
            "analytical_expected_npv": float(row.analytical_expected_npv),
            "mc_mean": float(mrow.mean_npv),
            "mc_median": float(mrow.median_npv),
            "mc_p05": float(mrow.p05_npv),
            "mc_p95": float(mrow.p95_npv),
            "mc_se": float(mrow.mc_standard_error),
            "z": float(mrow.standardized_discrepancy),
            "pr_negative": float(mrow.probability_negative_npv),
            "mean_reactivations": float(mrow.mean_reactivation_count),
            "runs": int(mrow.simulation_count),
        }
    _require(
        math.isclose(
            nine["base"]["medium_15pct"]["analytical_expected_npv"],
            p4_metrics["illustrative_reference_portfolio_npv_usd"],
            abs_tol=1e-6,
        ),
        "Reference NPV differs between Phase 3 and Phase 4",
    )

    survival = {
        s: {
            int(r.horizon_months): float(r.expected_reactivations)
            for r in p2_summary.loc[p2_summary.scenario_name.eq(s)].itertuples()
        }
        for s in SCENARIOS
    }
    base12 = p2_summary.loc[
        p2_summary.scenario_name.eq("base") & p2_summary.horizon_months.eq(12)
    ].iloc[0]
    sens12 = {
        r.sensitivity_case: {
            "accounts": int(r.cohort_accounts),
            "expected": float(r.expected_reactivations),
        }
        for r in p2_sens.loc[p2_sens.horizon_months.eq(12)].itertuples()
    }
    fin_sens = {r.sensitivity_case: float(r.expected_npv) for r in sens.itertuples(index=False)}
    be = {
        (
            r.metric
            if r.metric != "discount_response_hazard_multiplier"
            else f"hazard_multiplier_{r.commercial_tier}"
        ): float(r.threshold)
        for r in breakeven.itertuples(index=False)
    }
    _require(
        math.isclose(
            fin_sens["combined_adverse_hypothetical"],
            stress["committed_adverse_npv_usd"],
            abs_tol=STRESS_TOLERANCE_USD,
        ),
        "Committed stress differs from the frozen sensitivity output",
    )

    facts = {
        "provenance": {
            **{k: v for k, v in FROZEN.items() if k != "commits"},
            "commits": FROZEN["commits"],
            "phase3_seed": p3_metrics["seed"],
            "phase3_generator": p3_metrics["random_generator"],
            "financial_label": contract["financial_label"],
            "financial_provenance": contract["financial_provenance"],
        },
        "source": {
            "accounts": int(source["source_rows"]),
            "recorded_spend_usd": int(source["raw_recorded_spend_usd"]),
            "roots": p1["root_account_rows"],
            "children": p1["direct_child_rows"],
            "duplicate_account_rows": p1["duplicate_account_rows"],
            "unresolved_hierarchy_rows": p1["unresolved_hierarchy_rows"],
            "raw_region_variants": p1["raw_region_variants"],
            "canonical_regions": p1["canonical_regions"],
            "health_unknown": p1["health_unknown_rows"],
            "health_raw_nan": int(health_raw.get("nan", 0)),
            "health_raw_missing": int(health_raw.get("Missing", 0)),
            "partner_unknown": p1["partner_unknown_rows"],
            "ticket_sentinel": p1["ticket_sentinel_rows"],
            "valid_zero_tickets": p1["valid_zero_ticket_rows"],
            "quality_exception_rows": p1["quality_exception_rows"],
            "accounts_with_exceptions": p1["accounts_with_quality_exceptions"],
            "issue_counts": p1["issue_counts"],
            "inactivity_gap_6m": p1["inactivity_value_mismatch_rows"],
            "booking_date_exact_account_id_sequence": p1["booking_date_exact_account_id_sequence"],
            "contract_to_booking_days_unique": p1["contract_to_booking_days_unique"],
            "parent_partner_conflict_groups": p1["parent_partner_conflict_groups"],
        },
        "cohort": {
            "source_accounts": 2000,
            "modeled": cohort_counts["primary_reported_2y"],
            "conflicts": cohort_counts["eligibility_conflict"],
            "unknown": cohort_counts["eligibility_unknown"],
            "modeled_pct": float(
                cohort.loc[
                    cohort.scenario_cohort_status.eq("primary_reported_2y"), "percent_of_population"
                ].iloc[0]
            ),
            "modeled_roots": root_counts["all_modeled_roots"],
        },
        "survival": {
            "expected": survival,
            "base_12m_mean_probability": float(base12.mean_probability),
            "base_12m_min_probability": float(base12.min_probability),
            "base_12m_max_probability": float(base12.max_probability),
            "sensitivity_12m": sens12,
            "baseline_hazards": p2_assumptions["monthly_baseline_hazards"],
            "effects": p2_assumptions["assumed_log_hazard_effects"],
            "cox": {
                r.covariate: {
                    "true_beta": float(r.true_generating_coefficient),
                    "beta": float(r.estimated_log_hazard_coefficient),
                    "hr": float(r.estimated_hazard_ratio),
                    "lo": float(r.hazard_ratio_ci_lower_95),
                    "hi": float(r.hazard_ratio_ci_upper_95),
                }
                for r in cox.itertuples(index=False)
            },
            "cox_diagnostics": {
                "events": int(diag["n_events"]),
                "censored": int(diag["n_right_censored"]),
                "concordance_in_sample": float(diag["concordance_in_sample"]),
                "concordance_holdout": float(diag["concordance_independent_synthetic_holdout"]),
                "schoenfeld_p": diag["ph_schoenfeld_rank_p_values"],
            },
        },
        "financial": {
            "nine_cell": nine,
            "assumptions": {
                "monthly_gross_revenue": fin["monthly_gross_revenue_per_reactivated_account"],
                "contribution_margin": fin["contribution_margin"],
                "outreach_cost": fin["outreach_cost_per_target"],
                "activation_cost": fin["activation_cost_per_reactivation"],
                "annual_discount_rate": fin["annual_effective_financial_discount_rate"],
                "horizon_months": fin["horizon_months"],
                "simulations_per_cell": fin["simulations_per_cell"],
                "seed": fin["seed"],
            },
            "sensitivity": fin_sens,
            "break_even": be,
            "stress": stress,
            "max_abs_z": float(mc.standardized_discrepancy.abs().max()),
        },
        "gtm": {
            "channels": channel_counts,
            "channel_pct": {
                str(r.planning_disposition): float(r.percent_of_population)
                for r in channels.itertuples(index=False)
            },
            "rules": _counts(rules, "primary_rule_id"),
            "priority": priority_counts,
            "priority_evidence": {
                f"{r.commercial_priority_tier}|{r.evidence_quality_status}": int(r.account_count)
                for r in evidence.itertuples(index=False)
            },
            "readiness": readiness_counts,
            "service": _counts(service, "service_barrier_status"),
            "roots": root_counts,
            "authorized_contact_actions": p4_metrics["authorized_contact_actions"],
            "routed_candidates": sum(v for k, v in channel_counts.items() if k != "HOLD_REVIEW"),
            "policy": {
                "enterprise_min_gb": 37656,
                "critical_tickets": 5,
                "elevated_tickets": 3,
                "low_upper_npv": 161.51698172008832,
                "medium_upper_npv": 200.26496145151106,
            },
        },
        "disclosures": contract["executive_disclosures"],
    }
    _check_headline_values(facts)
    return facts


def _check_headline_values(f: dict) -> None:
    """Pin the headline values the Phase 5 brief requires; any drift is a hard failure."""
    nine = f["financial"]["nine_cell"]
    expected_nine = {
        ("conservative", "low_5pct"): 66866.14,
        ("conservative", "medium_15pct"): 46464.54,
        ("conservative", "high_30pct"): 15862.13,
        ("base", "low_5pct"): 241533.35,
        ("base", "medium_15pct"): 201501.66,
        ("base", "high_30pct"): 141454.13,
        ("optimistic", "low_5pct"): 464630.73,
        ("optimistic", "medium_15pct"): 399568.03,
        ("optimistic", "high_30pct"): 301973.98,
    }
    for (scenario, tier), value in expected_nine.items():
        _require(
            round(nine[scenario][tier]["analytical_expected_npv"], 2) == value,
            f"Nine-cell value drifted: {scenario}/{tier}",
        )
    s = f["survival"]["expected"]
    _require(
        (round(s["conservative"][12], 6), round(s["base"][12], 6), round(s["optimistic"][12], 6))
        == (66.329653, 128.724044, 206.205025),
        "Expected reactivations drifted",
    )
    g = f["gtm"]
    _require(
        g["channels"]
        == {
            "PARTNER_LED_CANDIDATE": 247,
            "DIRECT_ENTERPRISE_CANDIDATE": 66,
            "DIGITAL_NURTURE_CANDIDATE": 205,
            "HOLD_REVIEW": 626,
        },
        "Channel counts drifted",
    )
    _require(g["priority"] == {"HIGH": 288, "MEDIUM": 418, "LOW": 438}, "Priority drifted")
    _require(g["readiness"]["high_priority_health_unknown"] == 187, "High/unknown-health drifted")
    _require(g["roots"]["full_source_known_ownership_conflict_roots"] == 235, "Conflict roots")
    _require(g["roots"]["coordination_required_roots"] == 282, "Coordination roots drifted")
    _require(g["readiness"]["root_coordination_required"] == 1131, "Coordination accounts")
    c = f["cohort"]
    _require(
        (c["source_accounts"], c["modeled"], c["conflicts"], c["unknown"], c["modeled_roots"])
        == (2000, 1144, 562, 294, 295),
        "Cohort drifted",
    )
    src = f["source"]
    _require(
        (src["roots"], src["children"], src["quality_exception_rows"]) == (301, 1699, 4889),
        "Source facts drifted",
    )
    st = f["financial"]["stress"]
    _require(round(st["committed_adverse_npv_usd"], 6) == -124647.432973, "Committed stress")
    _require(round(st["alternative_compounded_npv_usd"], 6) == -124704.050145, "Alt stress")


if __name__ == "__main__":
    facts = load_validated_facts(ROOT)
    print(json.dumps(facts, indent=2, sort_keys=True, default=str))
