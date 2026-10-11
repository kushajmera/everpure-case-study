"""Build the synthetic reviewer notebook (runs without the confidential source)."""

# ruff: noqa: E501  # Long executable notebook cell strings.

import argparse
from pathlib import Path

import nbformat

md = nbformat.v4.new_markdown_cell
code = nbformat.v4.new_code_cell

cells = [
    md(
        "# Everpure | Synthetic reviewer demonstration (end to end)\n\n"
        "**SYNTHETIC REVIEWER DEMONSTRATION — INVENTED ACCOUNTS, NOT EVERPURE DATA.**\n\n"
        "This notebook runs the frozen production code on 22 invented `SYN_` accounts so a reviewer "
        "without the confidential assessment CSV can execute every stage: source hygiene, hierarchy "
        "resolution, DuckDB SQL (CTEs, LAG/LEAD, DENSE_RANK), the synthetic Cox lane, assumed-hazard "
        "reactivation probabilities, Monte Carlo NPV and the GTM routing rules. Numbers below describe "
        "the invented fixture only; the authoritative Everpure results are in the frozen aggregate "
        "outputs and the submission PDF."
    ),
    code(
        "from pathlib import Path\n"
        "import sys\n"
        "ROOT = Path.cwd().resolve()\n"
        "if ROOT.name == 'notebooks':\n"
        "    ROOT = ROOT.parent\n"
        "sys.path.insert(0, str(ROOT / 'src'))\n"
        "import pandas as pd\n"
        "import matplotlib.pyplot as plt\n"
        "from IPython.display import Markdown, display\n"
        "from everpure_case.reviewer_demo import LABEL, run_reviewer_demo\n"
        "from everpure_case.survival_synthetic import generate_synthetic_cohort, fit_synthetic_cox\n"
        "pd.set_option('display.width', 160)\n"
        "demo = run_reviewer_demo(ROOT, simulations=1000)\n"
        "display(Markdown(f'**{LABEL}**'))\n"
        "display(pd.Series(demo['checks'], name='check'))"
    ),
    md("## 1. Injected defects in the invented source rows"),
    code("display(demo['raw'].drop(columns='source_row_number'))"),
    md(
        "## 2. Cleaning and the exception register\n\n"
        "Region strings are trimmed and case-folded; `nan`/`Missing` health and blank partner flags stay "
        "unknown with an explicit flag; `999` tickets are excluded from valid counts; duplicate IDs are "
        "flagged, never merged."
    ),
    code(
        "exceptions = demo['exceptions']\n"
        "display(exceptions.groupby(['issue_code', 'severity', 'resolution']).size()\n"
        "        .rename('events').reset_index().sort_values('events', ascending=False))\n"
        "display(demo['hierarchy'].hierarchy_status.value_counts().rename('rows').to_frame())"
    ),
    md("## 3. DuckDB SQL on the cleaned synthetic accounts"),
    code(
        "display(Markdown('```sql\\n' + (ROOT / 'sql/spend_concentration.sql').read_text(encoding='utf-8') + '\\n```'))\n"
        "display(demo['sql']['spend_concentration'][['root_account_id', 'account_count', 'additive_recorded_spend_usd',\n"
        "                                            'spend_rank', 'cumulative_share']])\n"
        "display(demo['sql']['regional_spend'][['region', 'account_count', 'recorded_spend_usd', 'region_spend_rank']])"
    ),
    md(
        "## 4. Revenue-decay velocity SQL (LAG / LEAD / DENSE_RANK)\n\n"
        "The real extract has no account-period revenue, so decay velocity is demonstrated on the separate "
        "labeled fiscal-period fixture in `data/synthetic/`."
    ),
    code(
        "account_decay, root_decay = demo['decay']\n"
        "display(account_decay[['account_id', 'fiscal_period_index', 'period_revenue_usd', 'previous_revenue_usd',\n"
        "                       'next_revenue_usd', 'consecutive_pct_change', 'signed_change_usd_per_period',\n"
        "                       'comparison_status']])"
    ),
    md(
        "## 5. Survival analysis\n\n"
        "**Lane A** fits a genuine Cox proportional-hazards model to invented event histories and recovers "
        "the generating effects. **Lane B** applies the frozen assumption register "
        "(`docs/PHASE_2_ASSUMPTIONS.json`) to the invented cohort: P(T ≤ t) = 1 − exp(−λ·t·exp(xβ))."
    ),
    code(
        "model, coefficients, diagnostics, _ = fit_synthetic_cox(generate_synthetic_cohort())\n"
        "display(coefficients[['covariate', 'true_generating_coefficient', 'estimated_log_hazard_coefficient',\n"
        "                      'estimated_hazard_ratio', 'hazard_ratio_ci_lower_95', 'hazard_ratio_ci_upper_95']])\n"
        "display(pd.Series({k: diagnostics[k] for k in ('n_events', 'n_right_censored', 'concordance_in_sample',\n"
        "                                               'concordance_independent_synthetic_holdout')}))\n"
        "summary = demo['survival_summary']\n"
        "wide = summary.pivot(index='horizon_months', columns='scenario_name', values='expected_reactivations')\n"
        "display(wide[['conservative', 'base', 'optimistic']].round(3))\n"
        "ax = wide[['conservative', 'base', 'optimistic']].plot(marker='o', figsize=(7, 3.6))\n"
        "ax.set(xlabel='Months', ylabel='Expected cumulative first reactivations',\n"
        "       title='SYNTHETIC fixture | assumed-hazard scenarios (not additive across horizons)')\n"
        "plt.show()"
    ),
    md(
        "## 6. Monte Carlo NPV across three discount tiers\n\n"
        "Closed-form expected NPV versus 1,000 simulated replications per cell, with common random numbers "
        "and the frozen Phase 3 unit economics."
    ),
    code(
        "cells = demo['nine_cell']\n"
        "display(cells[['reactivation_scenario', 'commercial_discount_tier', 'analytical_expected_npv', 'mc_mean_npv',\n"
        "               'mc_p05_npv', 'mc_p95_npv', 'standardized_discrepancy']].round(2))\n"
        "assert cells.standardized_discrepancy.abs().max() < 4.5"
    ),
    md(
        "## 7. GTM routing, root coordination and the authorization gate\n\n"
        "Rules run in order R2 → R8; priority tiers and evidence flags never override a rule. "
        "The duplicate-ID record shows the R2 identity hold."
    ),
    code(
        "decisions = demo['decisions']\n"
        "display(decisions[['account_id', 'partner_status', 'health_status', 'valid_open_tickets', 'monthly_usage_gb',\n"
        "                   'primary_rule_id', 'planning_disposition', 'commercial_priority_tier',\n"
        "                   'evidence_quality_status', 'execution_authorized']])\n"
        "display(decisions.planning_disposition.value_counts().rename('accounts').to_frame())\n"
        "display(demo['roots'][['root_account_id', 'modeled_account_count', 'full_source_account_count',\n"
        "                       'root_coordination_required', 'reason_codes']])\n"
        "display(pd.Series(demo['identity_example'])[['primary_rule_id', 'planning_disposition', 'primary_reason_code']])\n"
        "assert not decisions.execution_authorized.any()\n"
        "print('Authorized customer-contact actions:', int(decisions.execution_authorized.sum()))"
    ),
    md(
        "## 8. What this notebook does not show\n\n"
        "It does not reproduce, sample or approximate the confidential Everpure source or any Everpure "
        "result. Reproducing the authoritative analysis requires the original CSV (Path A in the README). "
        "Probabilities and economics are assumption-based; no causal campaign uplift is identified; every "
        "route is planning-only."
    ),
]
ids = [
    "demo-intro",
    "demo-run",
    "demo-raw-md",
    "demo-raw",
    "demo-clean-md",
    "demo-clean",
    "demo-sql-md",
    "demo-sql",
    "demo-decay-md",
    "demo-decay",
    "demo-survival-md",
    "demo-survival",
    "demo-mc-md",
    "demo-mc",
    "demo-routing-md",
    "demo-routing",
    "demo-limits",
]
for cell, stable_id in zip(cells, ids, strict=True):
    cell["id"] = stable_id

notebook = nbformat.v4.new_notebook(
    cells=cells,
    metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
args = parser.parse_args()
path = Path(args.repo_root).resolve() / "notebooks/00_synthetic_reviewer_demo.ipynb"
path.parent.mkdir(parents=True, exist_ok=True)
nbformat.write(notebook, path)
print(path)
