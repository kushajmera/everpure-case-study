"""Build the Phase 4 notebook from safe aggregates and synthetic examples."""

# ruff: noqa: E501  # Long executable notebook cell strings.

import argparse
from pathlib import Path

import nbformat


def code(source: str):
    return nbformat.v4.new_code_cell(source)


cells = [
    nbformat.v4.new_markdown_cell(
        "# Everpure Phase 4 — conditional GTM routing\n\n"
        "The 1,144 account cohort is provisional and fiscally unconfirmed. "
        "All recommendations are planning only. The financial priority is an illustrative "
        "assumption-based model value; historical decay and ticket velocity are unavailable. "
        "Figures below use broad aggregates. The worked account example is synthetic."
    ),
    code(
        "from pathlib import Path\n"
        "import sys\n"
        "import pandas as pd\n"
        "import matplotlib.pyplot as plt\n"
        "from IPython.display import display\n"
        "ROOT = Path.cwd()\n"
        "sys.path.insert(0, str(ROOT / 'src'))\n"
        "from everpure_case.phase4_pipeline import validate_phase4_artifacts\n"
        "from everpure_case.gtm_policy import load_policy\n"
        "from everpure_case.gtm_routing import route_account\n"
        "validate_phase4_artifacts(ROOT)\n"
        "out = ROOT / 'outputs/phase4'\n"
        "channels = pd.read_csv(out / 'routing_channel_summary.csv')\n"
        "priority = pd.read_csv(out / 'commercial_priority_summary.csv')\n"
        "service = pd.read_csv(out / 'service_barrier_summary.csv')\n"
        "roots = pd.read_csv(out / 'root_coordination_summary.csv')\n"
        "cohort = pd.read_csv(out / 'cohort_reconciliation_summary.csv')\n"
        "assert channels.account_count.sum() == 1144\n"
        "assert cohort.account_count.sum() == 2000\n"
        "assert roots.loc[roots.measure.eq('all_modeled_roots'), 'root_count'].iloc[0] == 295\n"
        "display(channels[['planning_disposition', 'account_count', 'percent_of_population']])"
    ),
    code(
        "fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout='constrained')\n"
        "channels.plot.barh(x='planning_disposition', y='account_count', ax=axes[0,0], legend=False, color='#327b83')\n"
        "axes[0,0].set_title('Conditional planning routes | n=1,144')\n"
        "priority.plot.bar(x='commercial_priority_tier', y='account_count', ax=axes[0,1], legend=False, color='#559c83')\n"
        "axes[0,1].set_title('Illustrative NPV priority | n=1,144')\n"
        "service.plot.barh(x='service_barrier_status', y='account_count', ax=axes[1,0], legend=False, color='#a87843')\n"
        "axes[1,0].set_title('Ticket snapshot classification | n=1,144')\n"
        "cohort.plot.bar(x='scenario_cohort_status', y='account_count', ax=axes[1,1], legend=False, color='#596b91')\n"
        "axes[1,1].set_title('Source cohort reconciliation | n=2,000')\n"
        "for ax in axes.flat:\n"
        "    ax.set_ylabel('Accounts')\n"
        "    ax.set_xlabel('')\n"
        "plt.show()"
    ),
    nbformat.v4.new_markdown_cell(
        "## Synthetic routing example\n\nNo real customer identifiers are used or displayed."
    ),
    code(
        "example = {'partner_status': 'NO', 'health_status': 'UNKNOWN', "
        "'valid_open_tickets': None, 'monthly_usage_gb': 40000.0, "
        "'ticket_sentinel': True, 'has_manual_review_exceptions': True, "
        "'identity_valid': True, 'expected_account_npv': 250.0, "
        "'expected_reactivation_probability': 0.2}\n"
        "decision = route_account(example, load_policy(ROOT))\n"
        "display(pd.DataFrame([decision])[['planning_disposition', 'commercial_priority_tier', "
        "'evidence_quality_status', 'additional_reason_codes', 'execution_authorized']])\n"
        "assert decision['execution_authorized'] is False"
    ),
]

for cell, stable_id in zip(
    cells,
    ("phase4-intro", "phase4-inputs", "phase4-figure", "phase4-example-intro", "phase4-example"),
    strict=True,
):
    cell["id"] = stable_id

notebook = nbformat.v4.new_notebook(
    cells=cells,
    metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
)
parser = argparse.ArgumentParser(description="Build deterministic Phase 4 notebook")
parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
args = parser.parse_args()
path = Path(args.repo_root).resolve() / "notebooks/04_gtm_routing.ipynb"
path.parent.mkdir(parents=True, exist_ok=True)
nbformat.write(notebook, path)
print(path)
