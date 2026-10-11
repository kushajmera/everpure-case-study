"""End-to-end reviewer demonstration on invented accounts; runs without confidential data.

Every analytical step calls the frozen production code: the Phase 1 orchestrator (run on
a temporary synthetic root), the DuckDB SQL files, the Phase 2 assumed-hazard engine,
the Phase 3 cash-flow and Monte Carlo functions and the Phase 4 routing rules and
policy. The invented ``SYN_`` accounts demonstrate mechanics only. Nothing here
reproduces, samples or approximates the confidential Everpure source or its results.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from everpure_case.config import SOURCE_RELATIVE_PATH
from everpure_case.financial_model import account_expectation, event_times, pathwise, summarize
from everpure_case.gtm_policy import load_policy
from everpure_case.gtm_routing import CHANNELS, route_account
from everpure_case.ingestion import read_source
from everpure_case.phase4_pipeline import _root_record
from everpure_case.pipeline import run_pipeline
from everpure_case.reactivation_scenarios import load_assumptions, project_accounts
from everpure_case.synthetic_demo import execute_synthetic_demo

LABEL = "SYNTHETIC REVIEWER DEMONSTRATION — INVENTED ACCOUNTS, NOT EVERPURE DATA"
FIXTURE = Path("data/synthetic/reviewer_demo/accounts.csv")
TIERS = {"low_5pct": 0.05, "medium_15pct": 0.15, "high_30pct": 0.30}
PARTNER = {"1.00000000": "YES", "0.00000000": "NO", "": "UNKNOWN"}


def _phase1(root: Path) -> tuple[dict, dict[str, pd.DataFrame]]:
    """Run the real Phase 1 orchestrator against a temporary root holding only the fixture."""
    with tempfile.TemporaryDirectory(prefix="everpure_reviewer_demo_") as tmp:
        work = Path(tmp)
        shutil.copytree(root / "sql", work / "sql")
        target = work / SOURCE_RELATIVE_PATH
        target.parent.mkdir(parents=True)
        shutil.copyfile(root / FIXTURE, target)
        metrics = run_pipeline(work)
        out = work / "outputs/phase1"
        frames = {
            name: pd.read_csv(out / f"{name}.csv", dtype=str, keep_default_na=False)
            for name in (
                "cleaned_accounts",
                "account_hierarchy",
                "account_quality_summary",
                "data_quality_exceptions",
                "regional_spend",
                "spend_concentration",
                "account_opportunity",
                "hierarchy_exceptions",
            )
        }
    return metrics, frames


def _modeling_frame(frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Join Phase 1 outputs exactly as the Phase 2 loader does, keyed by source row."""
    accounts = (
        frames["cleaned_accounts"]
        .merge(
            frames["account_hierarchy"][
                ["source_row_number", "root_account_id", "hierarchy_status"]
            ],
            on="source_row_number",
            validate="one_to_one",
        )
        .merge(
            frames["account_quality_summary"][
                ["source_row_number", "has_manual_review_exceptions"]
            ],
            on="source_row_number",
            validate="one_to_one",
        )
    )
    identity_ok = accounts.hierarchy_status.eq("resolved") & ~accounts.account_id.duplicated(
        keep=False
    )
    return accounts, accounts.loc[identity_ok].sort_values("account_id").reset_index(drop=True)


def _financials(projected: pd.DataFrame, assumptions_p3: dict, simulations: int, seed: int):
    base12 = projected.loc[
        projected.scenario_name.eq("base") & projected.horizon_months.eq(12)
    ].sort_values("account_id")
    lp = base12.assumed_log_hazard_linear_predictor.to_numpy(dtype=float)
    hazards_by_scenario = {
        s: float(
            projected.loc[projected.scenario_name.eq(s), "assumed_baseline_hazard_per_month"].iloc[
                0
            ]
        )
        * np.exp(lp)
        for s in ("conservative", "base", "optimistic")
    }
    generator = np.random.Generator(np.random.PCG64(seed))
    uniforms = generator.random((simulations, len(lp)))
    uniforms = np.clip(uniforms, np.nextafter(0.0, 1.0), np.nextafter(1.0, 0.0))
    cells, account_values = [], {}
    for scenario, hazards in hazards_by_scenario.items():
        times = event_times(uniforms, hazards)  # common random numbers across all nine cells
        for tier, discount in TIERS.items():
            expectation = account_expectation(hazards, assumptions_p3, discount)
            analytic = float(expectation.expected_account_npv.sum())
            run, _ = pathwise(times, assumptions_p3, discount)
            stats = summarize(run, analytic)
            cells.append(
                {
                    "reactivation_scenario": scenario,
                    "commercial_discount_tier": tier,
                    "modeled_accounts": len(lp),
                    "analytical_expected_npv": analytic,
                    "mc_mean_npv": stats["mean_npv"],
                    "mc_p05_npv": stats["p05_npv"],
                    "mc_p95_npv": stats["p95_npv"],
                    "mc_standard_error": stats["mc_standard_error"],
                    "standardized_discrepancy": stats["standardized_discrepancy"],
                    "probability_negative_npv": stats["probability_negative_npv"],
                    "demonstration_label": LABEL,
                }
            )
            account_values[(scenario, tier)] = expectation.assign(
                account_id=base12.account_id.to_numpy()
            )
    return pd.DataFrame(cells), account_values


def _routing(modeled: pd.DataFrame, reference: pd.DataFrame, policy: dict) -> pd.DataFrame:
    joined = modeled.merge(reference, on="account_id", validate="one_to_one")
    rows = []
    for a in joined.itertuples(index=False):
        tickets = None if a.tickets_clean == "" else float(a.tickets_clean)
        usage = None if a.monthly_usage_gb_num == "" else float(a.monthly_usage_gb_num)
        record = {
            "partner_status": PARTNER[a.partner_managed_clean],
            "health_status": a.health_clean or "UNKNOWN",
            "valid_open_tickets": tickets,
            "monthly_usage_gb": usage,
            "ticket_sentinel": a.ticket_sentinel == "True",
            "has_manual_review_exceptions": a.has_manual_review_exceptions == "True",
            "identity_valid": True,
            "expected_account_npv": a.expected_account_npv,
            "expected_reactivation_probability": a.expected_reactivation_probability,
        }
        rows.append(
            {
                "account_id": a.account_id,
                "parent_account_id": a.parent_account_id,
                "root_account_id": a.root_account_id,
                **record,
                **route_account(record, policy),
            }
        )
    return pd.DataFrame(rows)


def run_reviewer_demo(
    repo_root: str | Path, *, simulations: int = 1000, seed: int = 20261009
) -> dict:
    """Run the full synthetic workflow and return labeled frames and checks."""
    root = Path(repo_root).resolve()
    raw = read_source(root / FIXTURE)
    if not raw.account_id.str.startswith("SYN_").all():
        raise ValueError("Reviewer fixture must contain invented SYN_ identifiers only")
    metrics, frames = _phase1(root)
    accounts, identity_ok = _modeling_frame(frames)
    cohort = identity_ok.loc[
        identity_ok.eligibility_comparison_status.isin(["agree_eligible", "disagree", "unknown"])
    ]
    assumptions_p2 = load_assumptions(root)
    projected, survival_summary = project_accounts(cohort, assumptions_p2)
    projected = projected.drop(columns=["source_baseline_sha"]).assign(demonstration_label=LABEL)
    survival_summary = survival_summary.assign(demonstration_label=LABEL)
    assumptions_p3 = json.loads(
        (root / "docs/PHASE_3_FINANCIAL_ASSUMPTIONS.json").read_text(encoding="utf-8")
    )
    nine_cell, account_values = _financials(projected, assumptions_p3, simulations, seed)
    reference = account_values[("base", "medium_15pct")][
        ["account_id", "expected_account_npv", "expected_reactivation_probability"]
    ]
    policy = load_policy(root)
    modeled = cohort.loc[cohort.reported_2y_eligible.eq("True")]
    decisions = _routing(modeled, reference, policy)
    full = accounts.loc[accounts.hierarchy_status.eq("resolved")]
    roots = pd.DataFrame(
        [
            _root_record(root_id, group, full.loc[full.root_account_id.eq(root_id)])
            for root_id, group in decisions.groupby("root_account_id", sort=True)
        ]
    )
    duplicate = accounts.loc[accounts.account_id.duplicated(keep=False)].iloc[0]
    identity_example = route_account(
        {
            "partner_status": PARTNER[duplicate.partner_managed_clean],
            "health_status": duplicate.health_clean or "UNKNOWN",
            "valid_open_tickets": None
            if duplicate.tickets_clean == ""
            else float(duplicate.tickets_clean),
            "monthly_usage_gb": None,
            "ticket_sentinel": duplicate.ticket_sentinel == "True",
            "has_manual_review_exceptions": True,
            "identity_valid": False,
            "expected_account_npv": 0.0,
            "expected_reactivation_probability": 0.0,
        },
        policy,
    )
    checks = {
        "fixture_ids_invented": bool(raw.account_id.str.startswith("SYN_").all()),
        "phase1_reconciles": metrics["sql_regional_spend_usd"] == metrics["raw_recorded_spend_usd"],
        "duplicate_ids_flagged": int(
            frames["data_quality_exceptions"].issue_code.eq("DUPLICATE_ACCOUNT_ID").sum()
        ),
        "sentinels_excluded": bool(
            accounts.loc[accounts.ticket_sentinel.eq("True"), "tickets_clean"].eq("").all()
        ),
        "probabilities_monotone_in_horizon": bool(
            projected.pivot_table(
                index=["account_id", "scenario_name"],
                columns="horizon_months",
                values="cumulative_reactivation_probability",
            )
            .diff(axis=1)
            .iloc[:, 1:]
            .gt(0)
            .all()
            .all()
        ),
        "max_abs_mc_z": float(nine_cell.standardized_discrepancy.abs().max()),
        "channels_valid": bool(decisions.planning_disposition.isin(CHANNELS).all()),
        "execution_authorized_count": int(decisions.execution_authorized.sum()),
        "identity_example_rule": identity_example["primary_rule_id"],
    }
    return {
        "label": LABEL,
        "raw": raw,
        "phase1_metrics": metrics,
        "exceptions": frames["data_quality_exceptions"],
        "hierarchy": frames["account_hierarchy"],
        "sql": {
            k: frames[k] for k in ("regional_spend", "spend_concentration", "account_opportunity")
        },
        "decay": execute_synthetic_demo(root),
        "cohort": cohort,
        "projected": projected,
        "survival_summary": survival_summary,
        "nine_cell": nine_cell,
        "decisions": decisions,
        "roots": roots,
        "identity_example": identity_example,
        "checks": checks,
    }
