"""Independent small-case checks for Phase 3 event and cash-flow semantics."""

import copy
import hashlib
import json
import shutil
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import everpure_case.financial_model as financial_model
from everpure_case.financial_model import (
    account_expectation,
    discount_factor,
    event_times,
    fingerprint,
    pathwise,
    summarize,
    validate_assumptions,
)
from everpure_case.phase2_pipeline import validate_phase3_artifacts as validate_phase2_artifacts
from everpure_case.phase3_pipeline import (
    _inputs,
    _scenario_hazards,
    break_even,
    financial_sensitivity,
    financial_tolerance,
    run_pipeline,
    validate_phase3_artifacts,
    validate_phase4_handoff,
    write_csv,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def model_input():
    return _inputs(ROOT)


@pytest.fixture
def output_scratch():
    path = ROOT / "tests" / f"_scratch_{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)


def test_assumption_fingerprint_and_ranges(model_input):
    contract, a, _, _ = model_input
    assert fingerprint(a) == a["fingerprint_sha256"]
    for key, value in (
        ("monthly_gross_revenue_per_reactivated_account", -1),
        ("contribution_margin", 1.01),
        ("annual_effective_financial_discount_rate", -0.01),
        ("simulations_per_cell", 999),
        ("simulations_per_cell", 2000),
        ("horizon_months", 24),
    ):
        altered = copy.deepcopy(a)
        altered[key] = value
        altered["fingerprint_sha256"] = fingerprint(altered)
        with pytest.raises(ValueError):
            validate_assumptions(altered, contract)
    altered = copy.deepcopy(a)
    del altered["retention_policy"]
    altered["fingerprint_sha256"] = fingerprint(altered)
    with pytest.raises(ValueError):
        validate_assumptions(altered, contract)
    altered = copy.deepcopy(a)
    altered["commercial_discount_tiers"]["high_30pct"] = 0.35
    altered["fingerprint_sha256"] = fingerprint(altered)
    with pytest.raises(ValueError, match="Unsupported commercial"):
        validate_assumptions(altered, contract)


@pytest.mark.parametrize(
    "field,value",
    [
        ("horizon_months", 24),
        ("simulations_per_cell", 2000),
        ("commercial_discount_tiers", {"low_5pct": 0.05, "medium_15pct": 0.15, "high_30pct": 0.35}),
    ],
)
def test_unsupported_config_rejected_before_output(
    field,
    value,
    output_scratch,
    monkeypatch,
    model_input,
):
    _, assumptions, _, _ = model_input
    altered = copy.deepcopy(assumptions)
    altered[field] = value
    altered["fingerprint_sha256"] = fingerprint(altered)
    assumption_path = output_scratch / "unsupported_assumptions.json"
    assumption_path.write_text(json.dumps(altered), encoding="utf-8")
    monkeypatch.setattr(
        financial_model, "ASSUMPTIONS_PATH", assumption_path.relative_to(ROOT).as_posix()
    )
    out = output_scratch / "uncreated_phase3"
    with pytest.raises(ValueError, match="Unsupported"):
        run_pipeline(ROOT, out)
    assert not out.exists()


def test_inverse_transform_and_nested_events():
    u = np.array([[0.2, 0.8], [0.4, 0.6]])
    h = np.array([0.01, 0.02])
    t = event_times(u, h)
    np.testing.assert_allclose(t, -np.log1p(-u) / h)
    np.testing.assert_array_less(event_times(u, h * 2), t)
    assert np.isinf(event_times(u, np.zeros(2))).all()
    assert ((t <= 3) <= (t <= 6)).all()
    assert ((t <= 6) <= (t <= 12)).all()
    for bad_u, bad_h in (([[0]], h), ([[1]], h), ([[np.nan]], h), (u, [-1, 1])):
        with pytest.raises(ValueError):
            event_times(bad_u, bad_h)


def test_exact_billing_cost_timing_and_bridge(model_input):
    _, a, _, _ = model_input
    t = np.array([[0.5, 5.2, 11.5, 12.5, np.inf, 0.0]])
    run, monthly = pathwise(t, a, 0.15)
    assert run.reactivation_count.iloc[0] == 4
    assert run.billed_account_count.iloc[0] == 3
    assert monthly.loc[monthly.month == 1, "mean_gross_revenue"].iloc[0] == 1000
    assert monthly.loc[monthly.month == 2, "mean_gross_revenue"].iloc[0] == 2000
    assert monthly.loc[monthly.month == 6, "mean_gross_revenue"].iloc[0] == 2000
    assert monthly.loc[monthly.month == 7, "mean_gross_revenue"].iloc[0] == 3000
    assert run.outreach_cost.iloc[0] == 600
    assert run.activation_cost.iloc[0] == 800
    expected_activation_pv = 200 * discount_factor(np.array([0, 0.5, 5.2, 11.5]), 0.12).sum()
    assert run.pv_activation_cost.iloc[0] == pytest.approx(expected_activation_pv)
    assert monthly.mean_pv_net_cashflow.sum() == pytest.approx(run.npv.iloc[0])
    assert monthly.loc[monthly.month == 0, "mean_activation_cost"].iloc[0] == 200
    assert run.npv.iloc[0] == pytest.approx(
        run.pv_contribution.iloc[0] - run.pv_activation_cost.iloc[0] - 600
    )


def test_zero_boundaries_and_closed_form(model_input):
    _, a, _, _ = model_input
    no_event = account_expectation(np.array([0.0]), a, 0.15)
    assert no_event.expected_account_npv.iloc[0] == -100
    run, monthly = pathwise(np.array([[np.inf]]), a, 0.15)
    assert run.npv.iloc[0] == -100
    assert monthly.mean_pv_net_cashflow.sum() == -100
    zero = copy.deepcopy(a)
    zero.update(
        {
            "annual_effective_financial_discount_rate": 0,
            "monthly_gross_revenue_per_reactivated_account": 0,
            "outreach_cost_per_target": 0,
            "activation_cost_per_reactivation": 0,
        }
    )
    assert account_expectation(np.array([0.0, 0.1]), zero, 1).expected_account_npv.sum() == 0
    np.testing.assert_allclose(discount_factor(np.array([0, 6, 12]), 0), 1)
    assert discount_factor(12, 0.12) == pytest.approx(1 / 1.12)
    with pytest.raises(ValueError):
        discount_factor(1, -0.01)
    h = 0.1
    oracle = account_expectation(np.array([h]), a, 0.15)
    d = np.log1p(0.12) / 12
    activation = 200 * h / (h + d) * (1 - np.exp(-(h + d) * 12))
    contribution = (
        1000
        * 0.85
        * 0.6
        * sum(discount_factor(m, 0.12) * (1 - np.exp(-h * (m - 1))) for m in range(1, 13))
    )
    assert oracle.expected_pv_activation_cost.iloc[0] == pytest.approx(activation)
    assert oracle.expected_pv_contribution.iloc[0] == pytest.approx(contribution)


@pytest.mark.parametrize("monthly_revenue", [1000.0, 25000.0, 100000.0])
def test_financial_csv_round_trip_and_cent_corruption(
    monthly_revenue,
    output_scratch,
    model_input,
):
    _, assumptions, _, _ = model_input
    altered = copy.deepcopy(assumptions)
    altered["monthly_gross_revenue_per_reactivated_account"] = monthly_revenue
    account = account_expectation(np.array([0.012]), altered, 0.15)
    path = output_scratch / "account.csv"
    write_csv(path, account)
    reread = pd.read_csv(path)
    bridged = (
        reread.expected_pv_contribution.iloc[0]
        - reread.expected_pv_activation_cost.iloc[0]
        - reread.allocated_outreach_cost.iloc[0]
    )
    scale = (
        abs(reread.expected_pv_contribution.iloc[0])
        + abs(reread.expected_pv_activation_cost.iloc[0])
        + abs(reread.allocated_outreach_cost.iloc[0])
    )
    assert abs(reread.expected_account_npv.iloc[0] - bridged) <= financial_tolerance(scale)
    assert financial_tolerance(scale) < 0.01
    assert abs(reread.expected_account_npv.iloc[0] + 0.01 - bridged) > financial_tolerance(scale)
    run, _ = pathwise(np.array([[0.5, 11.5]]), altered, 0.15)
    write_csv(path, run)
    reread_run = pd.read_csv(path)
    pv_bridge = (
        reread_run.pv_contribution.iloc[0]
        - reread_run.pv_activation_cost.iloc[0]
        - reread_run.outreach_cost.iloc[0]
    )
    assert abs(reread_run.npv.iloc[0] - pv_bridge) <= financial_tolerance(
        reread_run.pv_contribution.iloc[0]
    )


def test_summary_statistics():
    frame = pd.DataFrame({"npv": [-10.0, 0.0, 10.0], "reactivation_count": [0, 1, 2]})
    s = summarize(frame, 1.0)
    assert s["mean_npv"] == 0
    assert s["median_npv"] == 0
    assert s["sd_npv"] == 10
    assert s["p05_npv"] == -9
    assert s["p95_npv"] == 9
    assert s["probability_negative_npv"] == pytest.approx(1 / 3)
    assert s["mc_standard_error"] == pytest.approx(10 / np.sqrt(3))


def test_phase2_identity_and_reconciliation(model_input):
    _, a, detail, base = model_input
    totals = {
        "conservative": (16.965, 33.672, 66.330),
        "base": (33.672, 66.330, 128.724),
        "optimistic": (55.555, 108.348, 206.205),
    }
    previous = None
    for scenario, expected in totals.items():
        h = _scenario_hazards(detail, base, scenario)
        for month, count in zip((3, 6, 12), expected, strict=True):
            assert (-np.expm1(-h * month)).sum() == pytest.approx(count, abs=0.001)
        if previous is not None:
            assert (h >= previous).all()
        previous = h
    result = break_even(_scenario_hazards(detail, base, "base"), a)
    assert len(result) == 6
    assert result.loc[result.metric == "minimum_monthly_gross_revenue", "threshold"].iloc[0] > 0
    stress = financial_sensitivity(_scenario_hazards(detail, base, "base"), a)
    adverse = stress.loc[stress.sensitivity_case == "combined_adverse_hypothetical"].iloc[0]
    assert adverse.expected_npv == pytest.approx(-124647.43297306923, abs=0.01)
    altered = json.loads(adverse.altered_inputs_json)
    assert altered["retention_paid_months"] == 3
    assert altered["monthly_gross_revenue_per_reactivated_account"] == 750


def test_complete_pipeline_and_local_handoff(output_scratch, model_input, monkeypatch):
    source_hash = hashlib.sha256(
        (ROOT / "data/raw/Case_Study_1_Install_Base_Reactivation.csv").read_bytes()
    ).hexdigest()
    phase2_path = ROOT / "outputs/phase2/reactivation_scenario_probabilities.csv"
    phase2_hash = hashlib.sha256(phase2_path.read_bytes()).hexdigest()
    out = output_scratch / "phase3"
    metrics = run_pipeline(ROOT, out)
    assert (
        metrics["scenario_cells"],
        metrics["run_records"],
        metrics["local_account_signal_rows"],
    ) == (9, 9000, 10296)
    runs = pd.read_csv(out / "monte_carlo_run_results.csv")
    summary = pd.read_csv(out / "monte_carlo_npv_summary.csv")
    local = pd.read_csv(out / "local_only/account_economic_signals.csv")
    assert (
        runs.groupby(["reactivation_scenario", "commercial_discount_tier"]).size() == 1000
    ).all()
    assert len(summary) == 9
    assert summary.standardized_discrepancy.abs().max() < 4.5
    for row in summary.itertuples(index=False):
        subset = local.loc[
            (local.reactivation_scenario == row.reactivation_scenario)
            & (local.commercial_discount_tier == row.commercial_discount_tier)
        ]
        assert subset.expected_account_npv.sum() == pytest.approx(
            row.analytic_expected_npv, abs=0.01
        )
        assert not subset.fiscal_eligibility_confirmed.any()
    contract = json.loads((out / "phase4_input_contract.json").read_text(encoding="utf-8"))
    assert (
        contract["local_account_input"]["sha256"]
        == hashlib.sha256(
            (out / "local_only/account_economic_signals.csv").read_bytes()
        ).hexdigest()
    )
    assert hashlib.sha256(phase2_path.read_bytes()).hexdigest() == phase2_hash
    assert (
        hashlib.sha256(
            (ROOT / "data/raw/Case_Study_1_Install_Base_Reactivation.csv").read_bytes()
        ).hexdigest()
        == source_hash
    )
    assert validate_phase3_artifacts(ROOT, output_dir=out, mode="handoff")["verified_cells"] == 9
    with pytest.raises(ValueError, match="notebook or figures"):
        validate_phase3_artifacts(ROOT, output_dir=out, mode="complete")

    aggregate = out / "monthly_cashflow_summary.csv"
    original_aggregate = aggregate.read_bytes()
    aggregate.write_bytes(original_aggregate + b"\n")
    with pytest.raises(ValueError, match="hash"):
        validate_phase3_artifacts(ROOT, output_dir=out)
    aggregate.write_bytes(original_aggregate)

    contract_path = out / "phase4_input_contract.json"
    manifest_path = out / "manifest.json"
    original_contract = contract_path.read_bytes()
    original_manifest = manifest_path.read_bytes()
    changed = json.loads(original_contract)
    changed["phase3_financial_assumption_fingerprint_sha256"] = "0" * 64
    contract_path.write_text(json.dumps(changed), encoding="utf-8")
    changed_manifest = json.loads(original_manifest)
    for item in changed_manifest["files"]:
        if Path(item["path"]).name == contract_path.name:
            item["sha256"] = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(changed_manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="stale"):
        validate_phase3_artifacts(ROOT, output_dir=out)
    contract_path.write_bytes(original_contract)
    manifest_path.write_bytes(original_manifest)

    alternate = copy.deepcopy(model_input[1])
    alternate["assessment_brief_status"] += " changed"
    alternate["fingerprint_sha256"] = fingerprint(alternate)
    alternate_path = output_scratch / "fresh_but_stale_for_outputs.json"
    alternate_path.write_text(json.dumps(alternate), encoding="utf-8")
    with monkeypatch.context() as patcher:
        patcher.setattr(
            financial_model, "ASSUMPTIONS_PATH", alternate_path.relative_to(ROOT).as_posix()
        )
        with pytest.raises(ValueError, match="manifest identity"):
            validate_phase3_artifacts(ROOT, output_dir=out)

    aggregate.unlink()
    with pytest.raises(ValueError, match="missing file"):
        validate_phase3_artifacts(ROOT, output_dir=out)
    aggregate.write_bytes(original_aggregate)

    figure_dir = out / "figures"
    figure_dir.mkdir()
    figure_entries = []
    for figure in sorted((ROOT / "outputs/phase3/figures").glob("*.png")):
        target = figure_dir / figure.name
        shutil.copy2(figure, target)
        figure_entries.append(
            {
                "path": target.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    notebook = ROOT / "notebooks/03_monte_carlo_npv.ipynb"
    complete_manifest = json.loads(original_manifest)
    complete_manifest["figures"] = figure_entries
    complete_manifest["notebook"] = {
        "path": notebook.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(notebook.read_bytes()).hexdigest(),
    }
    manifest_path.write_text(json.dumps(complete_manifest), encoding="utf-8")
    assert validate_phase3_artifacts(ROOT, output_dir=out, mode="complete")["verified_cells"] == 9
    figure_path = figure_dir / "npv_distribution.png"
    figure_path.write_bytes(figure_path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="hash"):
        validate_phase3_artifacts(ROOT, output_dir=out, mode="complete")

    path = out / "local_only/account_economic_signals.csv"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="hash"):
        validate_phase4_handoff(out)


def test_phase2_probability_tamper_is_rejected(output_scratch):
    phase2 = ROOT / "outputs/phase2"
    for name in (
        "phase3_input_contract.json",
        "assumptions.json",
        "reactivation_scenario_probabilities.csv",
        "reactivation_scenario_summary.csv",
    ):
        shutil.copy2(phase2 / name, output_scratch / name)
    path = output_scratch / "reactivation_scenario_probabilities.csv"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="hash"):
        validate_phase2_artifacts(output_scratch)
