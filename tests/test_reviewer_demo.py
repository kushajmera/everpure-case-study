"""The synthetic reviewer demonstration runs the frozen code without confidential data."""

from pathlib import Path

import pandas as pd
import pytest

from everpure_case.reviewer_demo import LABEL, run_reviewer_demo

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def demo():
    return run_reviewer_demo(ROOT, simulations=400)


def test_fixture_is_invented_and_outputs_are_labeled(demo):
    assert demo["raw"].account_id.str.startswith("SYN_").all()
    assert demo["projected"].demonstration_label.eq(LABEL).all()
    assert demo["nine_cell"].demonstration_label.eq(LABEL).all()
    assert "source_baseline_sha" not in demo["projected"].columns


def test_hygiene_rules_fire_on_injected_defects(demo):
    issues = demo["exceptions"].issue_code.value_counts()
    assert issues["DUPLICATE_ACCOUNT_ID"] == 2
    assert issues["REGION_NORMALIZED"] == 6
    assert issues["UNKNOWN_HEALTH"] == 5
    assert issues["UNRESOLVED_PARTNER"] == 3
    assert issues["TICKET_SENTINEL_999"] == 2
    assert issues["INACTIVITY_CONTRADICTION"] == 1
    assert issues["MISSING_PARENT"] == 1
    status = demo["hierarchy"].hierarchy_status.value_counts()
    assert status.to_dict() == {"resolved": 19, "ambiguous_id": 2, "missing_parent": 1}
    assert demo["checks"]["sentinels_excluded"]
    assert demo["checks"]["phase1_reconciles"]


def test_assumed_probabilities_are_monotone_and_cumulative(demo):
    assert demo["checks"]["probabilities_monotone_in_horizon"]
    summary = demo["survival_summary"]
    assert set(summary.cohort_accounts) == {17}
    wide = summary.pivot(
        index="horizon_months", columns="scenario_name", values="expected_reactivations"
    )
    assert (wide["conservative"] < wide["base"]).all() and (wide["base"] < wide["optimistic"]).all()


def test_monte_carlo_reconciles_to_closed_form(demo):
    cells = demo["nine_cell"]
    assert len(cells) == 9
    assert cells.standardized_discrepancy.abs().max() < 4.5
    base = cells.set_index(["reactivation_scenario", "commercial_discount_tier"])
    npv = base.analytical_expected_npv
    assert npv["base", "low_5pct"] > npv["base", "medium_15pct"] > npv["base", "high_30pct"]


def test_every_routing_branch_and_the_authorization_gate(demo):
    d = demo["decisions"].set_index("account_id")
    expected = {
        "SYN_R01": "R5",
        "SYN_R02": "R6",
        "SYN_R05": "R7",
        "SYN_C03": "R3",
        "SYN_C14": "R3",
        "SYN_C04": "R4",
        "SYN_C06": "R4",
        "SYN_C13": "R6",
        "SYN_C15": "R8",
        "SYN_C05": "R6",
    }
    assert {k: d.loc[k, "primary_rule_id"] for k in expected} == expected
    assert "TICKET_SENTINEL_999" in d.loc["SYN_C05", "additional_reason_codes"]
    assert demo["identity_example"]["primary_rule_id"] == "R2"
    assert not d.execution_authorized.any()
    assert demo["checks"]["execution_authorized_count"] == 0


def test_root_coordination_sees_out_of_cohort_ownership(demo):
    roots = demo["roots"].set_index("root_account_id")
    assert "OUT_OF_COHORT_OWNERSHIP_CONFLICT" in roots.loc["SYN_R03", "reason_codes"]
    assert roots.root_coordination_required.all()
    assert pd.api.types.is_bool_dtype(roots.root_coordination_required)
