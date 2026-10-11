"""Create a source-ID-free Phase 3 notebook from aggregate artifacts."""

# ruff: noqa: E501  # Long strings are executable notebook cell source.

from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
FIGURE_LABEL = "Illustrative assumed financial economics — not observed Everpure revenue"


def markdown(value: str):
    return nbformat.v4.new_markdown_cell(value)


def code(value: str):
    return nbformat.v4.new_code_cell(value)


cells = [
    markdown(
        "# Everpure Phase 3 — illustrative Monte Carlo NPV\n\n"
        "**Financial scenario simulation, not an empirically calibrated revenue forecast.** "
        "The 1,144-account provisional cohort has no observed reactivation outcomes, post-event "
        "revenue, margins, treatment effects, or incremental profits. All six figures are model "
        "conditional and use aggregate outputs only. The externally verified assessment brief "
        "requires 1,000 runs and three discount tiers but gives no offer percentages or unit economics; "
        "5%, 15% and 30% are analyst-selected hypothetical offers."
    ),
    code(
        "from pathlib import Path\n"
        "import sys, json\n"
        "import numpy as np\n"
        "import pandas as pd\n"
        "import matplotlib.pyplot as plt\n"
        "from IPython.display import display\n"
        "ROOT = Path.cwd()\n"
        "sys.path.insert(0, str(ROOT / 'src'))\n"
        "from everpure_case.phase3_pipeline import _inputs, _scenario_hazards, validate_phase3_artifacts\n"
        "from everpure_case.financial_model import account_expectation, discount_factor\n"
        "out = ROOT / 'outputs/phase3'\n"
        "fig_dir = out / 'figures'\n"
        "fig_dir.mkdir(exist_ok=True)\n"
        "contract, assumptions, detail, base = _inputs(ROOT)\n"
        "validation = validate_phase3_artifacts(ROOT, mode='handoff')\n"
        "summary = pd.read_csv(out / 'monte_carlo_npv_summary.csv')\n"
        "runs = pd.read_csv(out / 'monte_carlo_run_results.csv')\n"
        "monthly = pd.read_csv(out / 'monthly_cashflow_summary.csv')\n"
        "sensitivity = pd.read_csv(out / 'financial_sensitivity.csv')\n"
        "break_even = pd.read_csv(out / 'discount_break_even.csv')\n"
        "reconciliation = json.loads((out / 'financial_reconciliation.json').read_text())\n"
        "assert len(runs) == 9000 and len(summary) == 9 and len(base) == 1144\n"
        "assert summary.standardized_discrepancy.abs().max() < reconciliation['z_limit']\n"
        "pd.DataFrame([{'source_sha256': contract['source_sha256'], "
        "'phase2_probability_sha256': contract['probability_artifact_sha256'], "
        "'financial_assumption_fingerprint': assumptions['fingerprint_sha256'], "
        "'provenance': assumptions['provenance']}])"
    ),
    markdown(
        "## Mechanics and assumptions\n\n"
        "One independent uniform per account and replication is shared across hazard scenarios. "
        "For monthly assumed hazard $h_i$, first-event time is "
        "$T_i=-\\log(1-U_i)/h_i$. The 5%, 15%, and 30% customer price discounts "
        "do not alter the hazard. A full month $m$ is billed only when $T_i\\le m-1$; "
        "cash is collected at month end. Outreach is paid at month zero and activation at $T_i$ "
        "when $T_i\\le12$. Contribution margin includes ongoing servicing costs. "
        "Retention through month 12 is assumed. Financial discounting uses the annual effective rate."
    ),
    code(
        "display(pd.DataFrame([{'monthly_gross_revenue_usd': assumptions['monthly_gross_revenue_per_reactivated_account'], "
        "'contribution_margin': assumptions['contribution_margin'], "
        "'outreach_per_target_usd': assumptions['outreach_cost_per_target'], "
        "'activation_per_event_usd': assumptions['activation_cost_per_reactivation'], "
        "'annual_financial_discount_rate': assumptions['annual_effective_financial_discount_rate'], "
        "'commercial_discount_tiers': str(assumptions['commercial_discount_tiers']), "
        "'simulations_per_cell': assumptions['simulations_per_cell'], 'seed': assumptions['seed']}]))\n"
        "hazards = _scenario_hazards(detail, base, 'base')\n"
        "oracle = account_expectation(hazards, assumptions, assumptions['commercial_discount_tiers']['medium_15pct'])\n"
        "assert np.isclose(oracle.expected_account_npv.sum(), "
        "summary.query(\"reactivation_scenario == 'base' and commercial_discount_tier == 'medium_15pct'\").analytic_expected_npv.iloc[0])\n"
        "display(summary[['reactivation_scenario', 'commercial_discount_tier', 'mean_npv', "
        "'analytic_expected_npv', 'mc_standard_error', 'standardized_discrepancy']].round(2))"
    ),
    markdown(
        "## Six aggregate figures\n\nAll money is USD for the 1,144-account provisional cohort."
    ),
    code(
        "center = runs.query(\"reactivation_scenario == 'base' and commercial_discount_tier == 'medium_15pct'\").npv\n"
        "fig, ax = plt.subplots(figsize=(9, 5))\n"
        "ax.hist(center / 1000, bins=30, color='#176b87', alpha=.85)\n"
        "for val, label, color in [(center.mean(), 'Mean', '#d62828'), (center.median(), 'Median', '#111111'), (center.quantile(.05), 'P5 downside', '#f77f00')]:\n"
        "    ax.axvline(val / 1000, color=color, linewidth=2, label=f'{label}: ${val/1000:,.1f}k')\n"
        "ax.set(xlabel='Net program NPV (USD thousands)', ylabel='Simulated replications', title='Base hazard · 15% customer discount · 1,000 runs')\n"
        "ax.legend()\n"
        f"fig.suptitle('{FIGURE_LABEL}', fontsize=10)\n"
        "fig.tight_layout(); fig.savefig(fig_dir / 'npv_distribution.png', dpi=150); display(fig); plt.close(fig)"
    ),
    code(
        "order = ['conservative', 'base', 'optimistic']\n"
        "tiers = ['low_5pct', 'medium_15pct', 'high_30pct']\n"
        "grid = summary.pivot(index='reactivation_scenario', columns='commercial_discount_tier', values='mean_npv').loc[order, tiers] / 1000\n"
        "fig, ax = plt.subplots(figsize=(8, 5))\n"
        "im = ax.imshow(grid, cmap='Blues', aspect='auto')\n"
        "for i in range(3):\n"
        "    for j in range(3): ax.text(j, i, f'${grid.iloc[i,j]:,.0f}k', ha='center', va='center', color='white' if grid.iloc[i,j] > grid.to_numpy().max()*.6 else 'black')\n"
        "ax.set(xticks=range(3), yticks=range(3), xticklabels=['5%', '15%', '30%'], yticklabels=order, xlabel='Commercial price discount', ylabel='Assumed hazard case', title='Mean illustrative NPV (USD thousands)')\n"
        f"fig.suptitle('{FIGURE_LABEL}', fontsize=10)\n"
        "fig.tight_layout(); fig.savefig(fig_dir / 'nine_cell_comparison.png', dpi=150); display(fig); plt.close(fig)"
    ),
    code(
        "s = summary.copy()\n"
        "s['scenario_order'] = pd.Categorical(s.reactivation_scenario, categories=['conservative','base','optimistic'], ordered=True)\n"
        "s = s.sort_values(['scenario_order', 'commercial_discount_rate']).reset_index(drop=True)\n"
        "labels = s.reactivation_scenario.str.title() + ' / ' + (100*s.commercial_discount_rate).astype(int).astype(str) + '%'\n"
        "y = np.arange(len(s))\n"
        "fig, ax = plt.subplots(figsize=(10, 6))\n"
        "ax.hlines(y, s.p05_npv/1000, s.p95_npv/1000, color='#176b87', linewidth=4, label='P5–P95 simulated outcomes')\n"
        "ax.scatter(s.mean_npv/1000, y, color='#d62828', zorder=3, label='Mean')\n"
        "ax.axvline(0, color='black', linewidth=1); ax.set(yticks=y, yticklabels=labels, xlabel='Net program NPV (USD thousands)', title='Conditional outcome ranges for 1,144 modeled accounts')\n"
        "ax.invert_yaxis(); ax.legend()\n"
        f"fig.suptitle('{FIGURE_LABEL}', fontsize=10)\n"
        "fig.tight_layout(); fig.savefig(fig_dir / 'npv_risk_ranges.png', dpi=150); display(fig); plt.close(fig)"
    ),
    code(
        "sel = sensitivity[sensitivity.changed_parameter.isin(['monthly_gross_revenue_per_reactivated_account', 'contribution_margin', 'outreach_cost_per_target', 'annual_effective_financial_discount_rate', 'hazard_multiplier', 'retention_paid_months']) & (sensitivity.sensitivity_case != 'baseline')].copy()\n"
        "sel = sel.sort_values('difference_from_baseline')\n"
        "plot_labels = {'hazard_1.5x':'Hazard ×1.5', 'hazard_0.5x':'Hazard ×0.5', 'monthly_gross_revenue_per_reactivated_account_1.25x':'Monthly revenue +25%', 'monthly_gross_revenue_per_reactivated_account_0.75x':'Monthly revenue −25%', 'contribution_margin_1.25x':'Margin +25%', 'contribution_margin_0.75x':'Margin −25%', 'outreach_cost_per_target_0.5x':'Outreach cost −50%', 'outreach_cost_per_target_1.5x':'Outreach cost +50%', 'financial_rate_0':'Financial rate 0%', 'financial_rate_0.24':'Financial rate 24%', 'retention_cap_3_paid_months':'Retention cap: 3 paid months', 'retention_cap_6_paid_months':'Retention cap: 6 paid months'}\n"
        "sel['plot_label'] = sel.sensitivity_case.map(plot_labels)\n"
        "assert sel.plot_label.notna().all()\n"
        "fig, ax = plt.subplots(figsize=(10, 6))\n"
        "ax.barh(sel.plot_label, sel.difference_from_baseline/1000, color=np.where(sel.difference_from_baseline>=0, '#2a9d8f', '#e76f51'))\n"
        "ax.axvline(0, color='black'); ax.set(xlabel='Change in analytical expected NPV (USD thousands)', title='One-at-a-time assumption sensitivity · base hazard / 15% offer')\n"
        f"fig.suptitle('{FIGURE_LABEL}', fontsize=10)\n"
        "fig.tight_layout(); fig.savefig(fig_dir / 'financial_sensitivity.png', dpi=150); display(fig); plt.close(fig)"
    ),
    code(
        "c = monthly.query(\"reactivation_scenario == 'base' and commercial_discount_tier == 'medium_15pct'\").sort_values('month')\n"
        "df = discount_factor(c.month.to_numpy(), assumptions['annual_effective_financial_discount_rate'])\n"
        "pv_gross = float((c.mean_gross_revenue * df).sum())\n"
        "pv_price_deduction = float((c.mean_commercial_discount_deduction * df).sum())\n"
        "pv_discounted_revenue = pv_gross - pv_price_deduction\n"
        "pv_margin_deduction = pv_discounted_revenue - float(c.mean_pv_contribution.sum())\n"
        "pv_activation = float(c.mean_pv_activation_cost.sum())\n"
        "outreach = float(c.mean_outreach_cost.sum())\n"
        "bridge = [('PV gross revenue', pv_gross), ('Price discounts', -pv_price_deduction), ('Costs within margin', -pv_margin_deduction), ('PV activation', -pv_activation), ('Outreach at t=0', -outreach)]\n"
        "assert np.isclose(sum(v for _,v in bridge), summary.query(\"reactivation_scenario == 'base' and commercial_discount_tier == 'medium_15pct'\").mean_npv.iloc[0])\n"
        "fig, ax = plt.subplots(figsize=(10, 5))\n"
        "running = 0\n"
        "for i,(name,value) in enumerate(bridge):\n"
        "    ax.bar(i, abs(value)/1000, bottom=min(running, running+value)/1000, color='#2a9d8f' if value>=0 else '#e76f51')\n"
        "    running += value\n"
        "ax.bar(len(bridge), running/1000, color='#176b87')\n"
        "ax.set(xticks=range(len(bridge)+1), xticklabels=[name for name,_ in bridge]+['Mean NPV'], ylabel='Present value (USD thousands)', title='Consistent PV bridge · base hazard / 15% offer')\n"
        "ax.tick_params(axis='x', rotation=30)\n"
        f"fig.suptitle('{FIGURE_LABEL}', fontsize=10)\n"
        "fig.tight_layout(); fig.savefig(fig_dir / 'financial_pv_bridge.png', dpi=150); display(fig); plt.close(fig)"
    ),
    code(
        "b = break_even.iloc[:4].copy()\n"
        "fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))\n"
        "axes[0].bar(['Required revenue', 'Assumed revenue'], [b.loc[b.metric=='minimum_monthly_gross_revenue','threshold'].iloc[0], assumptions['monthly_gross_revenue_per_reactivated_account']], color=['#e76f51','#176b87'])\n"
        "axes[0].set(ylabel='USD per reactivated account per month', title='Base hazard / 5% offer break-even')\n"
        "d = break_even[break_even.metric=='discount_response_hazard_multiplier']\n"
        "axes[1].bar(d.commercial_tier.str.replace('_',' '), d.threshold, color='#2a9d8f')\n"
        "axes[1].axhline(1, color='black', linestyle='--'); axes[1].set(ylabel='Hypothetical hazard multiplier', title='Response required to match 5% offer')\n"
        "axes[1].tick_params(axis='x', rotation=20)\n"
        f"fig.suptitle('{FIGURE_LABEL}', fontsize=10)\n"
        "fig.tight_layout(); fig.savefig(fig_dir / 'break_even_economics.png', dpi=150); display(fig); plt.close(fig)"
    ),
    markdown(
        "## Limits and Phase 4 handoff\n\n"
        "P5–P95 bars are simulated outcome quantiles, not confidence intervals for real value. "
        "The lowest discount mechanically yields the highest NPV because customer response "
        "is fixed across offers. The source spend period and parent-child consolidation rule "
        "are unknown, so historical spend never enters assumed monthly revenue. The Phase 4 "
        "contract identifies a confidential local account table and requires review or blocked "
        "states for unresolved eligibility, health, ownership, and quality. No routing is performed here."
    ),
    code(
        "phase4 = json.loads((out / 'phase4_input_contract.json').read_text())\n"
        "display(pd.DataFrame([{'contract_version': phase4['version'], 'local_account_rows': phase4['local_account_input']['expected_rows'], 'classification': phase4['local_account_input']['classification'], 'forecast_months': phase4['forecast_horizon_months'], 'currency': phase4['currency']}]))"
    ),
]

for index, cell in enumerate(cells):
    cell["id"] = f"phase3-{index:02d}"

notebook = nbformat.v4.new_notebook(cells=cells)
notebook.metadata.kernelspec = {"display_name": "Python 3", "language": "python", "name": "python3"}
nbformat.write(notebook, ROOT / "notebooks/03_monte_carlo_npv.ipynb")
print(f"Built Phase 3 notebook with {sum(cell.cell_type == 'code' for cell in cells)} code cells")
