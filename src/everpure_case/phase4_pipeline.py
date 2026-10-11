"""Validate frozen inputs, enrich source records, and emit planning-only GTM artifacts."""

import argparse
import hashlib
import io
import json
from pathlib import Path

import pandas as pd

from everpure_case.gtm_policy import canonical_hash, load_policy
from everpure_case.gtm_routing import CHANNELS, route_account
from everpure_case.phase3_pipeline import validate_phase3_artifacts
from everpure_case.reactivation_scenarios import load_phase1_accounts, reconcile_cohort
from everpure_case.source_integrity import EXPECTED_SHA256

LOCAL_FILES = (
    "account_routing_decisions.csv",
    "cohort_dispositions.csv",
    "root_coordination.csv",
)
SAFE_FILES = (
    "routing_channel_summary.csv",
    "commercial_priority_summary.csv",
    "priority_evidence_summary.csv",
    "data_readiness_summary.csv",
    "service_barrier_summary.csv",
    "root_coordination_summary.csv",
    "cohort_reconciliation_summary.csv",
    "scenario_priority_sensitivity.csv",
    "routing_rule_counts.csv",
    "metrics.json",
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )


def _csv(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False, float_format="%.17g")


def enrich(financial: pd.DataFrame, source: pd.DataFrame) -> pd.DataFrame:
    """One-to-one join with explicit cross-checks; reject contradictions."""
    if len(financial) != 1144 or financial.account_id.duplicated().any():
        raise ValueError("Invalid reference financial grain")
    if len(source) != 2000 or source.account_id.duplicated().any():
        raise ValueError("Invalid source feature grain")
    source = source.copy()
    source["source_partner_status"] = source.partner_managed_clean.map(
        {"1.00000000": "YES", "0.00000000": "NO", "": "UNKNOWN"}
    )
    if source.source_partner_status.isna().any():
        raise ValueError("Unrecognized partner state")
    fields = [
        "account_id",
        "root_account_id",
        "parent_account_id",
        "hierarchy_status",
        "eligibility_comparison_status",
        "source_partner_status",
        "health_clean",
        "tickets_clean",
        "ticket_sentinel",
        "monthly_usage_gb_num",
        "region_clean",
        "has_manual_review_exceptions",
        "years_inactive",
        "historical_spend_usd",
    ]
    joined = financial.merge(
        source[fields],
        on="account_id",
        how="left",
        validate="one_to_one",
        suffixes=("", "_source"),
        indicator=True,
    )
    if len(joined) != 1144 or not joined._merge.eq("both").all():
        raise ValueError("Missing source feature account")
    expected = {
        "root": joined.root_account_id.eq(joined.root_account_id_source),
        "cohort": joined.eligibility_comparison_status.eq("agree_eligible"),
        "health": joined.health_unknown.eq(joined.health_clean.eq("")),
        "partner": joined.partner_unknown.eq(joined.source_partner_status.eq("UNKNOWN")),
        "sentinel": joined.ticket_sentinel.eq(joined.ticket_sentinel_source.eq("True")),
        "tickets": joined.tickets_missing.eq(joined.tickets_clean.eq("")),
        "quality": joined.has_manual_review_exceptions.eq(
            joined.has_manual_review_exceptions_source.eq("True")
        ),
    }
    bad = [name for name, match in expected.items() if not match.all()]
    if bad:
        raise ValueError(f"Source-financial feature conflict: {bad}")
    joined = joined.drop(columns=["_merge"])
    return joined.sort_values("account_id").reset_index(drop=True)


def _decisions(joined: pd.DataFrame, policy: dict, contract: dict) -> pd.DataFrame:
    rows = []
    for a in joined.itertuples(index=False):
        ticket = None if a.tickets_clean == "" else float(a.tickets_clean)
        usage = None if a.monthly_usage_gb_num == "" else float(a.monthly_usage_gb_num)
        source = {
            "partner_status": a.source_partner_status,
            "health_status": a.health_clean or "UNKNOWN",
            "valid_open_tickets": ticket,
            "monthly_usage_gb": usage,
            "ticket_sentinel": a.ticket_sentinel_source == "True",
            "has_manual_review_exceptions": a.has_manual_review_exceptions,
            "identity_valid": a.hierarchy_status == "resolved"
            and a.root_account_id == a.root_account_id_source,
            "expected_account_npv": a.expected_account_npv,
            "expected_reactivation_probability": a.expected_reactivation_probability,
        }
        route = route_account(source, policy)
        rows.append(
            {
                "account_id": a.account_id,
                "parent_account_id": a.parent_account_id,
                "root_account_id": a.root_account_id,
                "partner_status": source["partner_status"],
                "health_status": source["health_status"],
                "valid_open_tickets": ticket,
                "ticket_sentinel": source["ticket_sentinel"],
                "monthly_usage_gb": usage,
                "region": a.region_clean,
                "source_reported_years_inactive": a.years_inactive,
                "historical_spend_usd_descriptive_only": a.historical_spend_usd,
                "financial_reference_scenario": policy["reference_scenario"],
                "financial_reference_commercial_tier": policy["reference_discount_tier"],
                "expected_account_npv": a.expected_account_npv,
                "expected_reactivation_probability": a.expected_reactivation_probability,
                "financial_provenance": contract["provenance"],
                "financial_label": contract["reporting_label"],
                "source_sha256": contract["source_sha256"],
                "phase2_assumption_fingerprint_sha256": contract[
                    "phase2_assumption_fingerprint_sha256"
                ],
                "phase3_financial_assumption_fingerprint_sha256": contract[
                    "phase3_financial_assumption_fingerprint_sha256"
                ],
                "hierarchy_coordination_required": False,
                "root_coordination_required": False,
                **route,
            }
        )
    return pd.DataFrame(rows)


def _root_record(root_id: str, group: pd.DataFrame, full: pd.DataFrame) -> dict:
    """Describe one modeled root with its complete source ownership context."""
    if full is None or not set(group.account_id).issubset(set(full.account_id)):
        raise ValueError("Modeled account missing from full-source root")
    channels = group.planning_disposition.value_counts()
    modeled_conflict = len(set(group.partner_status) - {"UNKNOWN"}) > 1
    full_statuses = set(
        full.partner_managed_clean.map({"1.00000000": "YES", "0.00000000": "NO", "": "UNKNOWN"})
    )
    if not full_statuses <= {"YES", "NO", "UNKNOWN"}:
        raise ValueError("Invalid full-source partner status")
    full_known_conflict = {"YES", "NO"}.issubset(full_statuses)
    full_unknown_ambiguity = "UNKNOWN" in full_statuses and bool(full_statuses & {"YES", "NO"})
    mixed_channel = group.planning_disposition.nunique() > 1
    reason = []
    if modeled_conflict:
        reason.append("MODELED_PARTNER_OWNERSHIP_CONFLICT")
    if full_known_conflict:
        reason.append("FULL_SOURCE_KNOWN_OWNERSHIP_CONFLICT")
    if full_known_conflict and not modeled_conflict:
        reason.append("OUT_OF_COHORT_OWNERSHIP_CONFLICT")
    if full_unknown_ambiguity:
        reason.append("FULL_SOURCE_UNKNOWN_OWNERSHIP_AMBIGUITY")
    if mixed_channel:
        reason.append("MIXED_PLANNING_CHANNELS")
    if len(group) > 1:
        reason.append("MULTI_ACCOUNT_ROOT_COORDINATION")
    return {
        "root_account_id": root_id,
        "modeled_account_count": len(group),
        "full_source_account_count": len(full),
        "out_of_cohort_account_count": len(full) - len(group),
        "modeled_root_present": group.account_id.eq(root_id).any(),
        "full_source_root_present": full.account_id.eq(root_id).any(),
        "modeled_child_count": group.parent_account_id.ne("").sum(),
        **{f"{channel.lower()}_count": int(channels.get(channel, 0)) for channel in CHANNELS},
        **{
            f"{tier.lower()}_priority_count": int(group.commercial_priority_tier.eq(tier).sum())
            for tier in ("HIGH", "MEDIUM", "LOW")
        },
        "mixed_partner_ownership": modeled_conflict,
        "modeled_membership_conflict": modeled_conflict,
        "full_source_known_ownership_conflict": full_known_conflict,
        "full_source_unknown_ownership_ambiguity": full_unknown_ambiguity,
        "mixed_planning_channels": mixed_channel,
        "root_coordination_required": len(group) > 1 or full_known_conflict,
        "reason_codes": "|".join(reason),
        "illustrative_sum_of_account_model_values_usd": group.expected_account_npv.sum(),
        "value_label": "ILLUSTRATIVE_SUM_OF_ACCOUNT_MODEL_VALUES",
    }


def _roots(decisions: pd.DataFrame, source: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Coordinate modeled decisions using ownership evidence from every source root member."""
    if source.account_id.duplicated().any() or source.root_account_id.eq("").any():
        raise ValueError("Invalid full-source hierarchy")
    source_groups = {key: group for key, group in source.groupby("root_account_id", sort=True)}
    roots = [
        _root_record(root_id, group, source_groups.get(root_id))
        for root_id, group in decisions.groupby("root_account_id", sort=True)
    ]
    frame = pd.DataFrame(roots)
    if (
        len(frame) != 295
        or frame.modeled_account_count.sum() != 1144
        or frame.full_source_account_count.sum() > len(source)
        or (frame.out_of_cohort_account_count < 0).any()
    ):
        raise ValueError("Modeled root reconciliation failed")
    needs = frame.set_index("root_account_id").root_coordination_required
    decisions = decisions.copy()
    decisions["hierarchy_coordination_required"] = decisions.root_account_id.map(needs)
    decisions["root_coordination_required"] = decisions.hierarchy_coordination_required
    decisions.loc[decisions.hierarchy_coordination_required, "additional_reason_codes"] += (
        "|ROOT_COORDINATION_REQUIRED"
    )
    return decisions, frame


def _cohort(source: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    cohort = reconcile_cohort(source)[["account_id", "root_account_id", "scenario_cohort_status"]]
    cohort = cohort.merge(
        decisions[["account_id", "planning_disposition", "primary_reason_code"]],
        on="account_id",
        how="left",
        validate="one_to_one",
    )
    missing = cohort.planning_disposition.isna()
    cohort.loc[missing, "planning_disposition"] = "HOLD_REVIEW"
    cohort.loc[
        missing & cohort.scenario_cohort_status.eq("eligibility_conflict"), "primary_reason_code"
    ] = "SOURCE_INACTIVITY_CONFLICT"
    cohort.loc[
        missing & cohort.scenario_cohort_status.eq("eligibility_unknown"), "primary_reason_code"
    ] = "SOURCE_INACTIVITY_UNKNOWN"
    cohort["financial_score_available"] = ~missing
    cohort["execution_authorized"] = False
    if (
        len(cohort) != 2000
        or cohort.account_id.duplicated().any()
        or (
            cohort.scenario_cohort_status.value_counts().to_dict()
            != {
                "primary_reported_2y": 1144,
                "eligibility_conflict": 562,
                "eligibility_unknown": 294,
            }
        )
    ):
        raise ValueError("Full population reconciliation failed")
    return cohort


def _summary(rows: pd.DataFrame, column: str, denominator: int, policy: dict) -> pd.DataFrame:
    result = rows.groupby(column, dropna=False).size().reset_index(name="account_count")
    result["population_denominator_accounts"] = denominator
    result["percent_of_population"] = 100 * result.account_count / denominator
    result["reference_scenario"] = policy["reference_scenario"]
    result["reference_discount_tier"] = policy["reference_discount_tier"]
    result["policy_version"] = policy["version"]
    result["provenance"] = policy["probability_label"]
    result["limitation"] = "PROVISIONAL_COHORT_FISCAL_UNCONFIRMED_PLANNING_ONLY"
    return result


def _safe(
    decisions: pd.DataFrame,
    cohort: pd.DataFrame,
    roots: pd.DataFrame,
    financial: pd.DataFrame,
    policy: dict,
) -> dict[str, pd.DataFrame]:
    out = {
        "routing_channel_summary.csv": _summary(decisions, "planning_disposition", 1144, policy),
        "commercial_priority_summary.csv": _summary(
            decisions, "commercial_priority_tier", 1144, policy
        ),
        "service_barrier_summary.csv": _summary(decisions, "service_barrier_status", 1144, policy),
        "routing_rule_counts.csv": _summary(decisions, "primary_rule_id", 1144, policy),
        "cohort_reconciliation_summary.csv": _summary(
            cohort, "scenario_cohort_status", 2000, policy
        ),
    }
    priority_evidence = (
        decisions.groupby(["commercial_priority_tier", "evidence_quality_status"])
        .size()
        .reset_index(name="account_count")
    )
    priority_evidence["population_denominator_accounts"] = 1144
    priority_evidence["policy_version"] = policy["version"]
    priority_evidence["reference_scenario"] = policy["reference_scenario"]
    priority_evidence["reference_discount_tier"] = policy["reference_discount_tier"]
    priority_evidence["limitation"] = "ILLUSTRATIVE_PRIORITY_NOT_EXECUTION_READINESS"
    out["priority_evidence_summary.csv"] = priority_evidence
    flags = [
        "partner_review_required",
        "health_review_required",
        "ticket_review_required",
        "root_coordination_required",
        "service_recovery_required",
    ]
    readiness = [
        {
            "measure": flag,
            "account_count": int(decisions[flag].sum()),
            "population_denominator_accounts": 1144,
            "policy_version": policy["version"],
            "reference_scenario": policy["reference_scenario"],
            "reference_discount_tier": policy["reference_discount_tier"],
            "limitation": "PROVISIONAL_PLANNING_ONLY",
        }
        for flag in flags
    ]
    readiness += [
        {
            "measure": "evidence_" + value,
            "account_count": int(count),
            "population_denominator_accounts": 1144,
            "policy_version": policy["version"],
            "reference_scenario": policy["reference_scenario"],
            "reference_discount_tier": policy["reference_discount_tier"],
            "limitation": "PROVISIONAL_PLANNING_ONLY",
        }
        for value, count in decisions.evidence_quality_status.value_counts().items()
    ]
    readiness.append(
        {
            "measure": "execution_authorized",
            "account_count": 0,
            "population_denominator_accounts": 1144,
            "policy_version": policy["version"],
            "reference_scenario": policy["reference_scenario"],
            "reference_discount_tier": policy["reference_discount_tier"],
            "limitation": "PROVISIONAL_PLANNING_ONLY",
        }
    )
    for flag, series in (
        ("high_priority_health_unknown", decisions.health_status.eq("UNKNOWN")),
        ("high_priority_partner_unknown", decisions.partner_status.eq("UNKNOWN")),
        ("high_priority_ticket_unknown", decisions.valid_open_tickets.isna()),
        ("high_priority_ticket_sentinel", decisions.ticket_sentinel),
    ):
        readiness.append(
            {
                "measure": flag,
                "account_count": int(
                    (decisions.commercial_priority_tier.eq("HIGH") & series).sum()
                ),
                "population_denominator_accounts": 288,
                "policy_version": policy["version"],
                "reference_scenario": policy["reference_scenario"],
                "reference_discount_tier": policy["reference_discount_tier"],
                "limitation": "HIGH_ILLUSTRATIVE_PRIORITY_MISSINGNESS",
            }
        )
    out["data_readiness_summary.csv"] = pd.DataFrame(readiness).sort_values("measure")
    out["root_coordination_summary.csv"] = pd.DataFrame(
        [
            {
                "measure": name,
                "root_count": int(value),
                "population_denominator_roots": 295,
                "policy_version": policy["version"],
                "reference_scenario": policy["reference_scenario"],
                "reference_discount_tier": policy["reference_discount_tier"],
                "limitation": "ROOT_VALUES_NOT_VERIFIED_CONSOLIDATED_REVENUE",
            }
            for name, value in {
                "all_modeled_roots": len(roots),
                "multi_account_roots": roots.modeled_account_count.gt(1).sum(),
                "modeled_known_ownership_conflict_roots": roots.modeled_membership_conflict.sum(),
                "full_source_known_ownership_conflict_roots": (
                    roots.full_source_known_ownership_conflict.sum()
                ),
                "full_source_unknown_ownership_ambiguity_roots": (
                    roots.full_source_unknown_ownership_ambiguity.sum()
                ),
                "mixed_planning_channel_roots": roots.mixed_planning_channels.sum(),
                "coordination_required_roots": roots.root_coordination_required.sum(),
            }.items()
        ]
    )
    financial = financial.copy()
    financial["high_priority_count"] = financial.expected_account_npv.gt(
        policy["priority"]["medium_upper_npv_usd"]
    ).astype(int)
    financial["low_priority_count"] = financial.expected_account_npv.le(
        policy["priority"]["low_upper_npv_usd"]
    ).astype(int)
    scenarios = (
        financial.groupby(["reactivation_scenario", "commercial_discount_tier"])
        .agg(
            modeled_account_count=("account_id", "size"),
            illustrative_sum_account_npv_usd=("expected_account_npv", "sum"),
            high_priority_count=("high_priority_count", "sum"),
            low_priority_count=("low_priority_count", "sum"),
        )
        .reset_index()
        .sort_values(["reactivation_scenario", "commercial_discount_tier"])
    )
    scenarios["medium_priority_count"] = (
        scenarios.modeled_account_count
        - scenarios.high_priority_count
        - scenarios.low_priority_count
    )
    scenarios["policy_version"] = policy["version"]
    scenarios["financial_label"] = policy["financial_label"]
    scenarios["limitation"] = "FIXED_BASE_15PCT_DOLLAR_CUTOFFS_NOT_RELATIVE_RERANKING"
    out["scenario_priority_sensitivity.csv"] = scenarios
    return out


def _compute_expected(
    root: Path,
) -> tuple[dict, dict, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict]:
    """Rebuild decisions in memory from authenticated upstream inputs, without writing."""
    policy = load_policy(root)
    validated = validate_phase3_artifacts(root, mode="complete")
    contract = json.loads(
        (root / "outputs/phase3/phase4_input_contract.json").read_text(encoding="utf-8")
    )
    if (
        contract["version"] != "phase3-to-phase4-v1"
        or contract["currency"] != "USD"
        or contract["financial_horizon_months"] != 12
        or contract["forecast_horizon_months"] != 12
        or contract["source_sha256"] != EXPECTED_SHA256
        or len(contract["local_account_input"]["schema"]) != 29
    ):
        raise ValueError("Unsupported Phase 3 handoff semantics")
    financial = pd.read_csv(
        root / contract["local_account_input"]["path"],
        dtype={"account_id": str, "root_account_id": str},
        float_precision="round_trip",
    )
    reference = financial.loc[
        financial.reactivation_scenario.eq(policy["reference_scenario"])
        & financial.commercial_discount_tier.eq(policy["reference_discount_tier"])
    ].copy()
    source = load_phase1_accounts(root)
    joined = enrich(reference, source)
    decisions = _decisions(joined, policy, contract)
    decisions, roots = _roots(decisions, source)
    cohort = _cohort(source, decisions)
    if (
        len(decisions) != 1144
        or decisions.account_id.duplicated().any()
        or not decisions.planning_disposition.isin(CHANNELS).all()
        or decisions.execution_authorized.any()
        or set(cohort.loc[cohort.financial_score_available, "account_id"])
        != set(decisions.account_id)
    ):
        raise ValueError("Routing invariant failed")
    safe = _safe(decisions, cohort, roots, financial, policy)
    metrics = {
        "version": "phase4-metrics-v1",
        "source_accounts": 2000,
        "modeled_accounts": 1144,
        "eligibility_conflicts": 562,
        "eligibility_unknown": 294,
        "modeled_roots": 295,
        "modeled_known_ownership_conflict_roots": int(roots.modeled_membership_conflict.sum()),
        "full_source_known_ownership_conflict_roots": int(
            roots.full_source_known_ownership_conflict.sum()
        ),
        "root_coordination_required_roots": int(roots.root_coordination_required.sum()),
        "root_coordination_required_accounts": int(decisions.root_coordination_required.sum()),
        "channels": decisions.planning_disposition.value_counts()
        .reindex(CHANNELS, fill_value=0)
        .to_dict(),
        "authorized_contact_actions": 0,
        "illustrative_reference_portfolio_npv_usd": float(decisions.expected_account_npv.sum()),
        "reference_scenario": policy["reference_scenario"],
        "reference_discount_tier": policy["reference_discount_tier"],
        "policy_fingerprint_sha256": canonical_hash(policy),
        "financial_provenance": contract["provenance"],
        "financial_label": contract["reporting_label"],
        "source_sha256": contract["source_sha256"],
        "phase2_assumption_fingerprint_sha256": contract["phase2_assumption_fingerprint_sha256"],
        "phase3_financial_assumption_fingerprint_sha256": validated[
            "financial_assumption_fingerprint_sha256"
        ],
    }
    return policy, contract, financial, decisions, cohort, roots, safe, metrics


def run_pipeline(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    policy, contract, financial, decisions, cohort, roots, safe, metrics = _compute_expected(root)
    out = root / "outputs/phase4"
    local = out / "local_only"
    local.mkdir(parents=True, exist_ok=True)
    for name, frame in zip(LOCAL_FILES, (decisions, cohort, roots), strict=True):
        _csv(local / name, frame)
    for name, frame in safe.items():
        _csv(out / name, frame)
    _json(out / "metrics.json", metrics)
    artifact_hashes = {name: _hash(out / name) for name in SAFE_FILES}
    handoff = {
        "version": "phase4-to-phase5-v2",
        "classification": "AGGREGATE_ONLY",
        "permitted_aggregate_files": artifact_hashes,
        "aggregate_schemas": {
            name: {
                "columns": list(frame.columns),
                "record_grain": ["reactivation_scenario", "commercial_discount_tier"]
                if name == "scenario_priority_sensitivity.csv"
                else ["commercial_priority_tier", "evidence_quality_status"]
                if name == "priority_evidence_summary.csv"
                else list(frame.columns[:1]),
            }
            for name, frame in safe.items()
        },
        "metrics_schema": {"keys": sorted(metrics)},
        "prohibited_local_only_files": [
            f"outputs/phase4/local_only/{name}" for name in LOCAL_FILES
        ],
        "cohort_denominators": {
            "source_accounts": 2000,
            "modeled_accounts": 1144,
            "modeled_roots": 295,
        },
        "reference_scenario": policy["reference_scenario"],
        "reference_discount_tier": policy["reference_discount_tier"],
        "currency": "USD",
        "financial_horizon_months": 12,
        "source_sha256": contract["source_sha256"],
        "phase2_assumption_fingerprint_sha256": contract["phase2_assumption_fingerprint_sha256"],
        "phase3_financial_assumption_fingerprint_sha256": contract[
            "phase3_financial_assumption_fingerprint_sha256"
        ],
        "phase4_policy_fingerprint_sha256": canonical_hash(policy),
        "financial_provenance": contract["provenance"],
        "financial_label": contract["reporting_label"],
        "executive_disclosures": policy["required_executive_disclosures"],
    }
    _json(out / "phase5_input_contract.json", handoff)
    manifest = {
        "version": "phase4-artifact-manifest-v2",
        "policy_fingerprint_sha256": canonical_hash(policy),
        "safe": {
            **artifact_hashes,
            "phase5_input_contract.json": _hash(out / "phase5_input_contract.json"),
        },
        "local_only": {name: _hash(local / name) for name in LOCAL_FILES},
    }
    notebook = root / "notebooks/04_gtm_routing.ipynb"
    if notebook.is_file():
        manifest["notebook"] = {
            "path": "notebooks/04_gtm_routing.ipynb",
            "sha256": _hash(notebook),
            "classification": "AGGREGATE_AND_SYNTHETIC_ONLY",
        }
    _json(out / "manifest.json", manifest)
    validate_phase4_artifacts(root)
    return metrics


def _grain(name: str, frame: pd.DataFrame) -> list[str]:
    if name == "scenario_priority_sensitivity.csv":
        return ["reactivation_scenario", "commercial_discount_tier"]
    if name == "priority_evidence_summary.csv":
        return ["commercial_priority_tier", "evidence_quality_status"]
    return list(frame.columns[:1])


def _compare_delivered(path: Path, expected: pd.DataFrame, grain: list[str]) -> None:
    """Compare every delivered field at its key after equivalent CSV round-tripping."""
    expected_csv = expected.to_csv(index=False, float_format="%.17g")
    canonical = pd.read_csv(io.StringIO(expected_csv), float_precision="round_trip")
    delivered = pd.read_csv(path, float_precision="round_trip")
    if (
        list(delivered.columns) != list(canonical.columns)
        or delivered.duplicated(grain).any()
        or canonical.duplicated(grain).any()
    ):
        raise ValueError(f"Phase 4 independent grain or schema mismatch: {path.name}")
    try:
        pd.testing.assert_frame_equal(
            delivered.set_index(grain).sort_index(),
            canonical.set_index(grain).sort_index(),
            check_dtype=False,
            check_exact=False,
            rtol=0,
            atol=1e-9,
        )
    except AssertionError as exc:
        raise ValueError(f"Phase 4 independent recomputation mismatch: {path.name}") from exc


def validate_phase4_artifacts(repo_root: str | Path) -> None:
    """Verify bytes, current upstream economics, and independently rebuilt semantics."""
    root = Path(repo_root).resolve()
    policy, contract, _, decisions, cohort, roots, safe, expected_metrics = _compute_expected(root)
    out = root / "outputs/phase4"
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    handoff = json.loads((out / "phase5_input_contract.json").read_text(encoding="utf-8"))
    notebook = manifest.get("notebook")
    if (
        manifest.get("version") != "phase4-artifact-manifest-v2"
        or set(manifest)
        != {"version", "policy_fingerprint_sha256", "safe", "local_only", "notebook"}
        or manifest.get("policy_fingerprint_sha256") != canonical_hash(policy)
        or set(manifest.get("safe", {})) != set(SAFE_FILES) | {"phase5_input_contract.json"}
        or set(manifest.get("local_only", {})) != set(LOCAL_FILES)
        or not isinstance(notebook, dict)
        or notebook.get("path") != "notebooks/04_gtm_routing.ipynb"
        or notebook.get("classification") != "AGGREGATE_AND_SYNTHETIC_ONLY"
        or _hash(root / notebook["path"]) != notebook.get("sha256")
    ):
        raise ValueError("Phase 4 artifact inventory or notebook mismatch")
    for name, digest in manifest["safe"].items():
        if _hash(out / name) != digest:
            raise ValueError(f"Phase 4 safe artifact hash mismatch: {name}")
    for name, digest in manifest["local_only"].items():
        if _hash(out / "local_only" / name) != digest:
            raise ValueError(f"Phase 4 local artifact hash mismatch: {name}")
    for name, frame in zip(LOCAL_FILES, (decisions, cohort, roots), strict=True):
        _compare_delivered(
            out / "local_only" / name,
            frame,
            ["root_account_id"] if name == "root_coordination.csv" else ["account_id"],
        )
    for name, frame in safe.items():
        _compare_delivered(out / name, frame, _grain(name, frame))
    actual_metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    if actual_metrics != expected_metrics:
        raise ValueError("Phase 4 independent metrics recomputation mismatch")
    expected_schemas = {
        name: {"columns": list(frame.columns), "record_grain": _grain(name, frame)}
        for name, frame in safe.items()
    }
    expected_handoff_fields = {
        "version": "phase4-to-phase5-v2",
        "classification": "AGGREGATE_ONLY",
        "aggregate_schemas": expected_schemas,
        "metrics_schema": {"keys": sorted(expected_metrics)},
        "prohibited_local_only_files": [
            f"outputs/phase4/local_only/{name}" for name in LOCAL_FILES
        ],
        "cohort_denominators": {
            "source_accounts": 2000,
            "modeled_accounts": 1144,
            "modeled_roots": 295,
        },
        "reference_scenario": policy["reference_scenario"],
        "reference_discount_tier": policy["reference_discount_tier"],
        "currency": contract["currency"],
        "financial_horizon_months": contract["financial_horizon_months"],
        "source_sha256": contract["source_sha256"],
        "phase2_assumption_fingerprint_sha256": contract["phase2_assumption_fingerprint_sha256"],
        "phase3_financial_assumption_fingerprint_sha256": contract[
            "phase3_financial_assumption_fingerprint_sha256"
        ],
        "phase4_policy_fingerprint_sha256": canonical_hash(policy),
        "financial_provenance": contract["provenance"],
        "financial_label": contract["reporting_label"],
        "executive_disclosures": policy["required_executive_disclosures"],
    }
    if (
        set(handoff) != set(expected_handoff_fields) | {"permitted_aggregate_files"}
        or any(handoff.get(key) != value for key, value in expected_handoff_fields.items())
        or handoff.get("permitted_aggregate_files")
        != {name: manifest["safe"][name] for name in SAFE_FILES}
    ):
        raise ValueError("Phase 5 handoff semantic mismatch")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build conditional Phase 4 GTM routing")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    print(json.dumps(run_pipeline(args.repo_root), indent=2))


if __name__ == "__main__":
    main()
