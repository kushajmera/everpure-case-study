"""Synthetic adversarial decisions and full confidential-cohort integration."""

import copy
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from everpure_case.gtm_policy import canonical_hash, load_policy
from everpure_case.gtm_routing import route_account
from everpure_case.phase3_pipeline import validate_phase3_artifacts
from everpure_case.phase4_pipeline import (
    _root_record,
    enrich,
    run_pipeline,
    validate_phase4_artifacts,
)
from everpure_case.reactivation_scenarios import load_phase1_accounts

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def phase4_repo():
    """Disposable complete upstream snapshot; no test rewrites authoritative outputs."""
    scratch = ROOT / "tests" / f"_scratch_{uuid.uuid4().hex}"
    scratch.mkdir()
    try:
        for directory in (
            "outputs/phase1",
            "outputs/phase2",
            "outputs/phase3",
            "outputs/phase4",
            "src",
            "scripts",
        ):
            shutil.copytree(
                ROOT / directory,
                scratch / directory,
                ignore=shutil.ignore_patterns("pytest-tmp", "__pycache__", "_scratch_*"),
            )
        for filename in (
            "data/raw/Case_Study_1_Install_Base_Reactivation.csv",
            "docs/PHASE_2_ASSUMPTIONS.json",
            "docs/PHASE_3_FINANCIAL_ASSUMPTIONS.json",
            "docs/PHASE_4_ROUTING_POLICY.json",
            "notebooks/03_monte_carlo_npv.ipynb",
            "notebooks/04_gtm_routing.ipynb",
        ):
            target = scratch / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / filename, target)
        yield scratch
    finally:
        shutil.rmtree(scratch)


def _rehash_phase4(root: Path) -> None:
    out = root / "outputs/phase4"
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name in manifest["safe"]:
        manifest["safe"][name] = hashlib.sha256((out / name).read_bytes()).hexdigest()
    for name in manifest["local_only"]:
        manifest["local_only"][name] = hashlib.sha256(
            (out / "local_only" / name).read_bytes()
        ).hexdigest()
    contract_path = out / "phase5_input_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["permitted_aggregate_files"] = {
        name: manifest["safe"][name]
        for name in manifest["safe"]
        if name != "phase5_input_contract.json"
    }
    contract_path.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest["safe"]["phase5_input_contract.json"] = hashlib.sha256(
        contract_path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


@pytest.fixture
def policy():
    return load_policy(ROOT)


@pytest.fixture
def synthetic():
    return {
        "partner_status": "NO",
        "health_status": "Green",
        "valid_open_tickets": 0.0,
        "monthly_usage_gb": 40000.0,
        "ticket_sentinel": False,
        "has_manual_review_exceptions": False,
        "identity_valid": True,
        "expected_account_npv": 250.0,
        "expected_reactivation_probability": 0.2,
    }


@pytest.mark.parametrize(
    ("changes", "channel", "rule"),
    [
        ({"partner_status": "YES"}, "PARTNER_LED_CANDIDATE", "R5"),
        ({}, "DIRECT_ENTERPRISE_CANDIDATE", "R6"),
        ({"monthly_usage_gb": 1000}, "DIGITAL_NURTURE_CANDIDATE", "R7"),
        ({"partner_status": "UNKNOWN"}, "HOLD_REVIEW", "R3"),
        ({"health_status": "Red"}, "HOLD_REVIEW", "R4"),
        ({"valid_open_tickets": 5}, "HOLD_REVIEW", "R4"),
        ({"identity_valid": False}, "HOLD_REVIEW", "R2"),
        ({"monthly_usage_gb": None}, "HOLD_REVIEW", "R8"),
    ],
)
def test_route_precedence(policy, synthetic, changes, channel, rule):
    synthetic.update(changes)
    routed = route_account(synthetic, policy)
    assert routed["planning_disposition"] == channel
    assert routed["primary_rule_id"] == rule
    assert routed["execution_authorized"] is False
    assert routed["recommended_action_type"] == "PLANNING_ONLY"
    assert routed["fiscal_eligibility_confirmed"] is False


def test_unknown_health_and_sentinel_are_explicit(policy, synthetic):
    synthetic.update(health_status="UNKNOWN", valid_open_tickets=None, ticket_sentinel=True)
    routed = route_account(synthetic, policy)
    assert routed["planning_disposition"] == "DIRECT_ENTERPRISE_CANDIDATE"
    assert routed["evidence_quality_status"] == "MATERIAL_REVIEW"
    assert routed["service_barrier_status"] == "UNKNOWN_SERVICE_EVIDENCE"
    assert "TICKET_SENTINEL_999" in routed["additional_reason_codes"]
    assert "HEALTH_UNKNOWN" in routed["additional_reason_codes"]
    assert routed["assumed_dormancy_persistence_12m"] == pytest.approx(0.8)
    assert routed["ticket_velocity_observed"] is False


def test_valid_zero_is_snapshot_not_velocity(policy, synthetic):
    routed = route_account(synthetic, policy)
    assert routed["service_barrier_status"] == "NO_OBSERVED_OPEN_BACKLOG"
    assert routed["ticket_velocity_observed"] is False


def test_threshold_ties(policy, synthetic):
    synthetic["expected_account_npv"] = policy["priority"]["low_upper_npv_usd"]
    assert route_account(synthetic, policy)["commercial_priority_tier"] == "LOW"
    synthetic["expected_account_npv"] = policy["priority"]["medium_upper_npv_usd"]
    assert route_account(synthetic, policy)["commercial_priority_tier"] == "MEDIUM"
    synthetic["monthly_usage_gb"] = policy["enterprise_scale_proxy"]["minimum_gb"]
    assert route_account(synthetic, policy)["primary_rule_id"] == "R6"


def test_actual_frozen_priority_boundaries(policy, synthetic):
    upper = float("200.26496145151106")
    below = math.nextafter(upper, -math.inf)
    above = math.nextafter(upper, math.inf)
    assert [
        route_account({**synthetic, "expected_account_npv": value}, policy)[
            "commercial_priority_tier"
        ]
        for value in (below, upper, above)
    ] == ["MEDIUM", "MEDIUM", "HIGH"]
    raw = pd.read_csv(
        ROOT / "outputs/phase3/local_only/account_economic_signals.csv",
        float_precision="round_trip",
    )
    reference = raw.loc[
        raw.reactivation_scenario.eq("base") & raw.commercial_discount_tier.eq("medium_15pct")
    ]
    values = reference.expected_account_npv
    assert values.eq(upper).sum() == 147
    assert values.eq(policy["priority"]["low_upper_npv_usd"]).sum() == 82
    assert (
        values.gt(upper).sum(),
        values.gt(policy["priority"]["low_upper_npv_usd"]).sum() - values.gt(upper).sum(),
        values.le(policy["priority"]["low_upper_npv_usd"]).sum(),
    ) == (288, 418, 438)


def test_policy_rejects_unsafe_changes(policy):
    unsafe = copy.deepcopy(policy)
    unsafe["execution_authorized"] = True
    with patch("pathlib.Path.read_text", return_value=json.dumps(unsafe)):
        with pytest.raises(ValueError, match="unsafe"):
            load_policy(ROOT)
    unsafe = copy.deepcopy(policy)
    unsafe["required_executive_disclosures"]["no_contact_authorization"] = "Approved for outreach"
    with patch("pathlib.Path.read_text", return_value=json.dumps(unsafe)):
        with pytest.raises(ValueError, match="unsafe"):
            load_policy(ROOT)
    assert canonical_hash(policy) == canonical_hash(dict(reversed(list(policy.items()))))


def test_source_enrichment_rejects_contradictions():
    source = load_phase1_accounts(ROOT)
    financial = pd.read_csv(
        ROOT / "outputs/phase3/local_only/account_economic_signals.csv",
        dtype={"account_id": str, "root_account_id": str},
        float_precision="round_trip",
    )
    financial = financial.loc[
        financial.reactivation_scenario.eq("base")
        & financial.commercial_discount_tier.eq("medium_15pct")
    ]
    assert len(enrich(financial, source)) == 1144
    shuffled = enrich(
        financial.sample(frac=1, random_state=17),
        source.sample(frac=1, random_state=19),
    )
    pd.testing.assert_frame_equal(enrich(financial, source), shuffled)
    duplicate = pd.concat([source, source.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="source feature grain"):
        enrich(financial, duplicate)
    missing = source.loc[~source.account_id.eq(financial.account_id.iloc[0])]
    with pytest.raises(ValueError, match="source feature grain"):
        enrich(financial, missing)
    altered = financial.copy()
    altered.loc[altered.index[0], "root_account_id"] = "WRONG"
    with pytest.raises(ValueError, match="root"):
        enrich(altered, source)
    altered = financial.copy()
    altered.loc[altered.index[0], "partner_unknown"] = not bool(altered.partner_unknown.iloc[0])
    with pytest.raises(ValueError, match="partner"):
        enrich(altered, source)


def test_full_pipeline_is_deterministic_and_private(phase4_repo):
    first = run_pipeline(phase4_repo)
    first_manifest = (phase4_repo / "outputs/phase4/manifest.json").read_bytes()
    second = run_pipeline(phase4_repo)
    assert first == second
    assert first_manifest == (phase4_repo / "outputs/phase4/manifest.json").read_bytes()
    validate_phase4_artifacts(phase4_repo)
    assert sum(first["channels"].values()) == 1144
    assert first["authorized_contact_actions"] == 0
    assert first["modeled_roots"] == 295
    decisions = pd.read_csv(
        phase4_repo / "outputs/phase4/local_only/account_routing_decisions.csv",
        float_precision="round_trip",
    )
    assert not decisions.execution_authorized.any()
    assert decisions.account_id.nunique() == 1144
    assert not any("account_id" in name for name in first)
    assert (
        decisions.loc[decisions.commercial_priority_tier.eq("HIGH"), "health_status"]
        .eq("UNKNOWN")
        .sum()
        == 187
    )
    assert first["full_source_known_ownership_conflict_roots"] == 235
    assert first["root_coordination_required_roots"] == 282
    assert first["root_coordination_required_accounts"] == 1131
    safe = phase4_repo / "outputs/phase4"
    for path in safe.glob("*"):
        if path.is_file():
            assert "ACC_" not in path.read_text(encoding="utf-8")


def test_rehashed_financial_input_rejected_by_independent_oracle():
    scratch = ROOT / "tests" / f"_scratch_{uuid.uuid4().hex}"
    out = scratch / "phase3"
    try:
        shutil.copytree(ROOT / "outputs/phase3", out, ignore=shutil.ignore_patterns("pytest-tmp"))
        account_path = out / "local_only/account_economic_signals.csv"
        accounts = pd.read_csv(account_path)
        accounts.loc[0, "expected_pv_contribution"] += 1.0
        accounts.loc[0, "expected_account_npv"] += 1.0
        accounts.to_csv(account_path, index=False, float_format="%.17g")
        summary_path = out / "monte_carlo_npv_summary.csv"
        summary = pd.read_csv(summary_path)
        cell = summary.reactivation_scenario.eq(accounts.loc[0, "reactivation_scenario"]) & (
            summary.commercial_discount_tier.eq(accounts.loc[0, "commercial_discount_tier"])
        )
        summary.loc[cell, "analytic_expected_npv"] += 1.0
        summary.loc[cell, "analytic_expected_pv_contribution"] += 1.0
        summary.to_csv(summary_path, index=False, float_format="%.17g")
        contract_path = out / "phase4_input_contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        relative = out.relative_to(ROOT).as_posix()
        contract["local_account_input"]["path"] = (
            f"{relative}/local_only/account_economic_signals.csv"
        )
        contract["local_account_input"]["sha256"] = hashlib.sha256(
            account_path.read_bytes()
        ).hexdigest()
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        manifest_path = out / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest["files"]:
            name = Path(entry["path"]).name
            entry["path"] = f"{relative}/{name}"
            entry["sha256"] = hashlib.sha256((out / name).read_bytes()).hexdigest()
        manifest["local_only"]["path"] = contract["local_account_input"]["path"]
        manifest["local_only"]["sha256"] = contract["local_account_input"]["sha256"]
        for entry in manifest["figures"]:
            name = Path(entry["path"]).name
            entry["path"] = f"{relative}/figures/{name}"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(ValueError, match="independent account oracle"):
            validate_phase3_artifacts(ROOT, output_dir=out, mode="handoff")
    finally:
        shutil.rmtree(scratch)


def test_out_of_cohort_parent_ownership_evidence():
    modeled = pd.DataFrame(
        [
            {
                "account_id": "SYN_CHILD",
                "parent_account_id": "SYN_PARENT",
                "partner_status": "NO",
                "planning_disposition": "DIRECT_ENTERPRISE_CANDIDATE",
                "commercial_priority_tier": "HIGH",
                "expected_account_npv": 100.0,
            }
        ]
    )
    full = pd.DataFrame(
        [
            {"account_id": "SYN_PARENT", "partner_managed_clean": "1.00000000"},
            {"account_id": "SYN_CHILD", "partner_managed_clean": "0.00000000"},
        ]
    )
    record = _root_record("SYN_PARENT", modeled, full)
    assert record["modeled_account_count"] == 1
    assert record["full_source_account_count"] == 2
    assert record["full_source_known_ownership_conflict"] is True
    assert record["modeled_membership_conflict"] is False
    assert record["root_coordination_required"] is True
    assert "OUT_OF_COHORT_OWNERSHIP_CONFLICT" in record["reason_codes"]
    full.loc[0, "partner_managed_clean"] = ""
    unknown = _root_record("SYN_PARENT", modeled, full)
    assert unknown["full_source_known_ownership_conflict"] is False
    assert unknown["full_source_unknown_ownership_ambiguity"] is True
    assert unknown["root_coordination_required"] is False
    with pytest.raises(ValueError, match="full-source root"):
        _root_record("SYN_OTHER", modeled, full.iloc[[0]])


@pytest.mark.parametrize(
    "name",
    [
        "commercial_priority_summary.csv",
        "data_readiness_summary.csv",
        "root_coordination_summary.csv",
    ],
)
def test_rehashed_aggregate_tampering_rejected(phase4_repo, name):
    out = phase4_repo / "outputs/phase4"
    path = out / name
    frame = pd.read_csv(path)
    count = "root_count" if name == "root_coordination_summary.csv" else "account_count"
    frame.loc[0, count] += 1
    frame.to_csv(path, index=False, float_format="%.17g")
    _rehash_phase4(phase4_repo)
    with pytest.raises(ValueError, match="independent recomputation"):
        validate_phase4_artifacts(phase4_repo)


def test_coordinated_unknown_partner_route_tampering_rejected(phase4_repo):
    out = phase4_repo / "outputs/phase4"
    path = out / "local_only/account_routing_decisions.csv"
    decisions = pd.read_csv(path, float_precision="round_trip")
    index = decisions.index[decisions.partner_status.eq("UNKNOWN")][0]
    account = decisions.loc[index, "account_id"]
    root_id = decisions.loc[index, "root_account_id"]
    decisions.loc[index, ["planning_disposition", "primary_rule_id", "primary_reason_code"]] = [
        "PARTNER_LED_CANDIDATE",
        "R5",
        "SOURCE_PARTNER_MANAGED",
    ]
    decisions.to_csv(path, index=False, float_format="%.17g")
    cohort_path = out / "local_only/cohort_dispositions.csv"
    cohort = pd.read_csv(cohort_path)
    cohort.loc[cohort.account_id.eq(account), "planning_disposition"] = "PARTNER_LED_CANDIDATE"
    cohort.to_csv(cohort_path, index=False)
    channels_path = out / "routing_channel_summary.csv"
    channels = pd.read_csv(channels_path)
    channels.loc[channels.planning_disposition.eq("HOLD_REVIEW"), "account_count"] -= 1
    channels.loc[channels.planning_disposition.eq("PARTNER_LED_CANDIDATE"), "account_count"] += 1
    channels["percent_of_population"] = 100 * channels.account_count / 1144
    channels.to_csv(channels_path, index=False, float_format="%.17g")
    rules_path = out / "routing_rule_counts.csv"
    rules = pd.read_csv(rules_path)
    rules.loc[rules.primary_rule_id.eq("R3"), "account_count"] -= 1
    rules.loc[rules.primary_rule_id.eq("R5"), "account_count"] += 1
    rules["percent_of_population"] = 100 * rules.account_count / 1144
    rules.to_csv(rules_path, index=False, float_format="%.17g")
    roots_path = out / "local_only/root_coordination.csv"
    roots = pd.read_csv(roots_path)
    roots.loc[roots.root_account_id.eq(root_id), "hold_review_count"] -= 1
    roots.loc[roots.root_account_id.eq(root_id), "partner_led_candidate_count"] += 1
    roots.to_csv(roots_path, index=False, float_format="%.17g")
    metrics_path = out / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["channels"]["HOLD_REVIEW"] -= 1
    metrics["channels"]["PARTNER_LED_CANDIDATE"] += 1
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _rehash_phase4(phase4_repo)
    with pytest.raises(ValueError, match="independent recomputation"):
        validate_phase4_artifacts(phase4_repo)


def test_handoff_disclosure_and_reference_tampering_rejected(phase4_repo):
    out = phase4_repo / "outputs/phase4"
    contract_path = out / "phase5_input_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["executive_disclosures"]["no_contact_authorization"] = "Approved for outreach"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    _rehash_phase4(phase4_repo)
    with pytest.raises(ValueError, match="handoff semantic"):
        validate_phase4_artifacts(phase4_repo)
    contract["executive_disclosures"] = load_policy(phase4_repo)["required_executive_disclosures"]
    contract["reference_scenario"] = "conservative"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    _rehash_phase4(phase4_repo)
    with pytest.raises(ValueError, match="handoff semantic"):
        validate_phase4_artifacts(phase4_repo)


def test_root_and_priority_rewrites_without_channel_change_rejected(phase4_repo):
    out = phase4_repo / "outputs/phase4"
    path = out / "local_only/account_routing_decisions.csv"
    original = path.read_bytes()
    decisions = pd.read_csv(path, float_precision="round_trip")
    index = decisions.index[decisions.root_coordination_required][0]
    decisions.loc[index, ["root_coordination_required", "hierarchy_coordination_required"]] = False
    decisions.to_csv(path, index=False, float_format="%.17g")
    _rehash_phase4(phase4_repo)
    with pytest.raises(ValueError, match="independent recomputation"):
        validate_phase4_artifacts(phase4_repo)
    path.write_bytes(original)
    decisions = pd.read_csv(path, float_precision="round_trip")
    index = decisions.index[decisions.commercial_priority_tier.eq("HIGH")][0]
    decisions.loc[index, "commercial_priority_tier"] = "MEDIUM"
    decisions.to_csv(path, index=False, float_format="%.17g")
    _rehash_phase4(phase4_repo)
    with pytest.raises(ValueError, match="independent recomputation"):
        validate_phase4_artifacts(phase4_repo)


def test_stale_phase3_assumptions_rejected_before_handoff(phase4_repo):
    from everpure_case.financial_model import fingerprint

    path = phase4_repo / "docs/PHASE_3_FINANCIAL_ASSUMPTIONS.json"
    assumptions = json.loads(path.read_text(encoding="utf-8"))
    assumptions["outreach_cost_per_target"] += 1
    assumptions["fingerprint_sha256"] = fingerprint(assumptions)
    path.write_text(json.dumps(assumptions), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest identity|stale"):
        validate_phase4_artifacts(phase4_repo)


def test_readme_notebook_sequence_and_verifier_integrity(phase4_repo):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(phase4_repo / "src")
    env["EVERPURE_SANDBOX_JUPYTER"] = "1"
    build = [sys.executable, "scripts/build_phase4_notebook.py"]
    for _ in range(2):
        subprocess.run(build, cwd=phase4_repo, env=env, check=True, capture_output=True)
        digest = hashlib.sha256(
            (phase4_repo / "notebooks/04_gtm_routing.ipynb").read_bytes()
        ).hexdigest()
        if _ == 0:
            first_digest = digest
        else:
            assert digest == first_digest
    subprocess.run(
        [sys.executable, "-m", "everpure_case.phase4_pipeline", "--repo-root", "."],
        cwd=phase4_repo,
        env=env,
        check=True,
        capture_output=True,
    )
    manifest_path = phase4_repo / "outputs/phase4/manifest.json"
    before_manifest = manifest_path.read_bytes()
    notebook_path = phase4_repo / "notebooks/04_gtm_routing.ipynb"
    before_notebook = notebook_path.read_bytes()
    verify = [sys.executable, "scripts/verify_phase4_notebook.py"]
    first_execution = subprocess.run(
        verify, cwd=phase4_repo, env=env, check=True, capture_output=True
    )
    second_execution = subprocess.run(
        verify, cwd=phase4_repo, env=env, check=True, capture_output=True
    )
    assert b"output_sha256=" in first_execution.stdout
    assert first_execution.stdout == second_execution.stdout
    validate_phase4_artifacts(phase4_repo)
    assert notebook_path.read_bytes() == before_notebook
    assert manifest_path.read_bytes() == before_manifest
    notebook_path.write_bytes(before_notebook + b"\n")
    rejected = subprocess.run(verify, cwd=phase4_repo, env=env, capture_output=True)
    assert rejected.returncode != 0
    assert manifest_path.read_bytes() == before_manifest
    notebook_path.write_bytes(before_notebook)
    manifest = json.loads(before_manifest)
    manifest["notebook"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    broken_manifest = manifest_path.read_bytes()
    rejected = subprocess.run(verify, cwd=phase4_repo, env=env, capture_output=True)
    assert rejected.returncode != 0
    assert manifest_path.read_bytes() == broken_manifest
