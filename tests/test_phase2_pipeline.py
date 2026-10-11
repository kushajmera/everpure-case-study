import hashlib
import json
import re
import shutil
import uuid
from pathlib import Path

import pandas as pd
import pytest

import everpure_case.phase2_pipeline as pipeline
from everpure_case.reactivation_scenarios import load_assumptions

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def output_scratch():
    path = ROOT / "tests" / f"_scratch_{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)


def test_scenario_lane_does_not_fit_or_read_synthetic(monkeypatch, output_scratch):
    monkeypatch.setattr(
        pipeline,
        "fit_synthetic_cox",
        lambda *_: (_ for _ in ()).throw(AssertionError("synthetic fit called")),
    )
    result = pipeline.run_scenario_lane(ROOT, output_scratch)
    assert result["primary_accounts"] == 1144
    assert not (output_scratch / "synthetic_survival_cohort.csv").exists()
    detail = pd.read_csv(output_scratch / "reactivation_scenario_probabilities.csv")
    assert len(detail) == 10296


def test_commit_eligible_notebook_and_guide_contain_no_source_account_ids():
    for path in (
        ROOT / "notebooks/02_survival_analysis.ipynb",
        ROOT / "docs/PHASE_2_INTERVIEW_DEFENSE.md",
    ):
        assert not re.search(rb"ACC_[0-9]+", path.read_bytes()), path
    notebook = json.loads(
        (ROOT / "notebooks/02_survival_analysis.ipynb").read_text(encoding="utf-8")
    )
    assert sum(cell["cell_type"] == "code" for cell in notebook["cells"]) == 12
    assert len(list((ROOT / "outputs/phase2/figures").glob("*.png"))) == 6


def test_pipeline_reproducible_and_phase1_unchanged(output_scratch):
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT / "outputs/phase1").rglob("*")
        if p.is_file()
    }
    out = output_scratch / "phase2"
    pipeline.run_pipeline(ROOT, out)
    first = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
    pipeline.run_pipeline(ROOT, out)
    second = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}
    assert first == second
    assert before == after
    detail = pd.read_csv(out / "reactivation_scenario_probabilities.csv")
    summary = pd.read_csv(out / "reactivation_scenario_summary.csv")
    pipeline.validate_phase3_artifacts(out)
    contract = json.loads((out / "phase3_input_contract.json").read_text(encoding="utf-8"))
    assert contract["version"] == "phase2-to-phase3-v2"
    assert not contract["event_semantics"]["sum_across_horizons"]
    assert not contract["event_semantics"]["independent_horizon_sampling"]
    assert contract["event_semantics"]["events_per_account_per_path_max"] == 1
    assert contract["time_basis"]["calendar_date_mapping_required"]
    changed = load_assumptions(ROOT)
    changed["monthly_baseline_hazards"]["base"] = 0.013
    with pytest.raises(ValueError, match="fingerprint"):
        pipeline.validate_phase3_contract(contract, changed, detail, summary)
    for row in summary.itertuples(index=False):
        subset = detail[
            (detail.scenario_name == row.scenario_name)
            & (detail.horizon_months == row.horizon_months)
        ]
        assert len(subset) == row.cohort_accounts == 1144
        assert (
            abs(subset.cumulative_reactivation_probability.sum() - row.expected_reactivations)
            < 1e-8
        )
    assumptions_path = out / "assumptions.json"
    tampered = json.loads(assumptions_path.read_text(encoding="utf-8"))
    tampered["monthly_baseline_hazards"]["base"] = 0.013
    assumptions_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint"):
        pipeline.validate_phase3_artifacts(out)
