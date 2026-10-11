import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from everpure_case.reactivation_scenarios import (
    PRIMARY_POLICY,
    assumption_fingerprint,
    engineer_features,
    load_assumptions,
    load_phase1_accounts,
    project_accounts,
    reconcile_cohort,
    scenario_sensitivity,
)
from everpure_case.source_integrity import EXPECTED_SHA256

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def inputs():
    return load_phase1_accounts(ROOT), load_assumptions(ROOT)


def test_source_cohort_and_missingness(inputs):
    accounts, _ = inputs
    assert len(accounts) == accounts.account_id.nunique() == 2000
    assert reconcile_cohort(accounts).scenario_cohort_status.value_counts().to_dict() == {
        "primary_reported_2y": 1144,
        "eligibility_conflict": 562,
        "eligibility_unknown": 294,
    }
    features = engineer_features(accounts)
    assert features.tickets_missing.sum() == 322
    assert features.tickets_clean.eq(0).sum() == 324
    assert features.health_unknown.sum() == 844
    assert features.partner_unknown.sum() == 654
    assert features.loc[features.ticket_sentinel, "tickets_clean"].isna().all()
    assert features.loc[features.tickets_clean.eq(0), "log1p_valid_tickets"].eq(0).all()
    assert features.account_id.is_unique


def test_scenario_grain_ordering_and_reconciliation(inputs):
    accounts, assumptions = inputs
    detail, summary = project_accounts(accounts, assumptions)
    assert len(detail) == 1144 * 9
    assert not detail.duplicated(["account_id", "scenario_name", "horizon_months"]).any()
    assert set(detail.scenario_name) == {"conservative", "base", "optimistic"}
    assert set(detail.horizon_months) == {3, 6, 12}
    assert detail.cumulative_reactivation_probability.between(0, 1).all()
    assert detail.source_baseline_sha.eq(EXPECTED_SHA256).all()
    assert detail.scenario_parameter_version.eq("phase2-assumptions-v1").all()
    assert not detail.to_csv(index=False).count("SYN_")
    across_scenarios = detail.pivot(
        index=["account_id", "horizon_months"],
        columns="scenario_name",
        values="cumulative_reactivation_probability",
    )
    assert (across_scenarios.conservative <= across_scenarios.base).all()
    assert (across_scenarios.base <= across_scenarios.optimistic).all()
    across_time = detail.pivot(
        index=["account_id", "scenario_name"],
        columns="horizon_months",
        values="cumulative_reactivation_probability",
    )
    assert (across_time[3] <= across_time[6]).all()
    assert (across_time[6] <= across_time[12]).all()
    assert summary.expected_reactivations.sum() == pytest.approx(
        detail.cumulative_reactivation_probability.sum()
    )
    assert detail.equals(project_accounts(accounts, assumptions)[0])


def test_alternative_policy_has_explicit_denominator(inputs):
    accounts, assumptions = inputs
    for policy, n in [
        (PRIMARY_POLICY, 1144),
        ("hypothetical_include_conflicts", 1706),
        ("hypothetical_include_all", 2000),
    ]:
        detail, summary = project_accounts(accounts, assumptions, policy)
        assert detail.account_id.nunique() == n
        assert summary.cohort_accounts.eq(n).all()
        assert detail.cohort_policy.eq(policy).all()


def test_missing_health_sensitivity_is_computed_without_changing_primary(inputs):
    accounts, assumptions = inputs
    before = project_accounts(accounts, assumptions)[0]
    sensitivity = scenario_sensitivity(accounts, assumptions)
    after = project_accounts(accounts, assumptions)[0]
    assert before.equals(after)
    rows = sensitivity.loc[sensitivity.horizon_months.eq(12)].set_index("sensitivity_case")
    assert rows.loc["primary_base", "expected_reactivations"] == pytest.approx(128.724044, abs=1e-5)
    assert rows.loc["unknown_health_as_yellow", "expected_reactivations"] == pytest.approx(
        121.090877, abs=1e-5
    )
    assert rows.loc["unknown_health_as_red", "expected_reactivations"] == pytest.approx(
        112.374350, abs=1e-5
    )
    known = accounts.loc[
        accounts.reported_2y_eligible.eq("True") & accounts.health_clean.ne(""), "health_clean"
    ]
    expected_effect = (
        known.eq("Yellow").mean() * assumptions["assumed_log_hazard_effects"]["health_yellow"]
        + known.eq("Red").mean() * assumptions["assumed_log_hazard_effects"]["health_red"]
    )
    assert rows.loc["unknown_health_observed_average", "unknown_health_log_effect"] == (
        pytest.approx(expected_effect)
    )
    assert rows.loc["unknown_health_observed_average", "expected_reactivations"] == (
        pytest.approx(120.269458, abs=1e-5)
    )
    assert rows.loc["unknown_health_observed_average", "cohort_accounts"] == 1144
    assert assumption_fingerprint(assumptions) != assumption_fingerprint(
        {**assumptions, "rationale": "changed content"}
    )


def test_adversarial_inputs(inputs):
    accounts, assumptions = inputs
    zero_spend = accounts.copy()
    zero_spend.loc[0, "historical_spend_usd"] = "0"
    assert engineer_features(zero_spend).equals(engineer_features(accounts))
    duplicate = accounts.iloc[[0]].copy()
    with pytest.raises(ValueError, match="Duplicate"):
        engineer_features(__import__("pandas").concat([accounts, duplicate]))
    invalid = accounts.copy()
    invalid.loc[0, "tickets_clean"] = "abc"
    with pytest.raises(ValueError, match="ticket"):
        engineer_features(invalid)
    for kwargs in [
        {"cohort_policy": "bad"},
        {"hazard_multiplier": -1},
        {"horizons": (-1,)},
        {"effect_scale": np.nan},
    ]:
        with pytest.raises(ValueError):
            project_accounts(accounts, assumptions, **kwargs)
    broken = json.loads(json.dumps(assumptions))
    broken["assumed_log_hazard_effects"]["is_child"] = np.inf
    with pytest.raises(ValueError, match="Non-finite"):
        project_accounts(accounts, broken)
    broken = json.loads(json.dumps(assumptions))
    broken["version"] = "stale"
    with pytest.raises(ValueError, match="version"):
        project_accounts(accounts, broken)
    broken = json.loads(json.dumps(assumptions))
    broken["monthly_baseline_hazards"]["base"] = -0.01
    with pytest.raises(ValueError, match="hazards"):
        project_accounts(accounts, broken)


def test_missing_source_and_modified_hash_fail(isolated_repo):
    # The Phase 1 fixture has only raw source, so missing analytical input is rejected.
    with pytest.raises(FileNotFoundError):
        load_phase1_accounts(isolated_repo)
    source = isolated_repo / "data/raw/Case_Study_1_Install_Base_Reactivation.csv"
    raw = source.read_bytes()
    source.write_bytes(raw + b"\n")
    with pytest.raises(ValueError, match="SHA-256"):
        load_phase1_accounts(isolated_repo)


def test_phase1_artifact_tampering_is_rejected(isolated_repo):
    source_phase1 = ROOT / "outputs/phase1"
    destination = isolated_repo / "outputs/phase1"
    destination.mkdir(parents=True)
    for name in (
        "cleaned_accounts.csv",
        "account_hierarchy.csv",
        "account_quality_summary.csv",
        "metrics.json",
    ):
        shutil.copyfile(source_phase1 / name, destination / name)
    assert len(load_phase1_accounts(isolated_repo)) == 2000
    hierarchy_path = destination / "account_hierarchy.csv"
    hierarchy = __import__("pandas").read_csv(hierarchy_path, dtype=str, keep_default_na=False)
    hierarchy.loc[0, "root_account_id"] = "UNRESOLVED_TEST_ROOT"
    hierarchy.to_csv(hierarchy_path, index=False)
    with pytest.raises(ValueError, match="root mapping"):
        load_phase1_accounts(isolated_repo)
    shutil.copyfile(source_phase1 / "account_hierarchy.csv", hierarchy_path)
    cleaned_path = destination / "cleaned_accounts.csv"
    cleaned = __import__("pandas").read_csv(cleaned_path, dtype=str, keep_default_na=False)
    sentinel_row = cleaned.index[cleaned.ticket_sentinel.eq("True")][0]
    cleaned.loc[sentinel_row, "tickets_clean"] = "999.00000000"
    cleaned.to_csv(cleaned_path, index=False)
    with pytest.raises(ValueError, match="ticket"):
        load_phase1_accounts(isolated_repo)
