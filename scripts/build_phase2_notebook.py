"""Build an interview-readable Phase 2 notebook from executable modules."""
# ruff: noqa: E501

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
cells = []


def md(value: str) -> None:
    cells.append(nbf.v4.new_markdown_cell(value))


def code(value: str) -> None:
    cells.append(nbf.v4.new_code_cell(value))


md("""# Everpure | Phase 2 survival analysis

**Methodology proof and assumed account scenarios, as of 2026-10-09.** The extract has no reactivation events, event timestamps, or censoring endpoints. The Cox model below is fitted only to synthetic event histories. Account probabilities are assumption based and uncalibrated.""")
code("""from pathlib import Path
import sys
ROOT = Path.cwd().resolve()
if ROOT.name == 'notebooks':
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / 'src'))
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import display
from everpure_case.source_integrity import verify_authoritative_source
from everpure_case.phase2_pipeline import run_pipeline
from everpure_case.survival import exponential_event_probability
from everpure_case.survival_synthetic import (
    BASELINE_HAZARD, FOLLOWUP_MONTHS, generate_synthetic_cohort, fit_synthetic_cox)
from everpure_case.reactivation_scenarios import load_phase1_accounts, load_assumptions, engineer_features
plt.style.use('seaborn-v0_8-whitegrid')
OUT = ROOT / 'outputs/phase2'
FIG = OUT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)
source_integrity = verify_authoritative_source(ROOT)
metrics = run_pipeline(ROOT)
display(source_integrity)""")

md("""## 1. Research question and data limits

We ask for the probability of reactivation within a future horizon from a defined prediction origin. This supplied extract contains account characteristics only. Its booking dates are deterministic functions of account IDs and cannot be reactivation events or event durations.""")

md("""## 2. Phase 1 integrity and cohort reconciliation

The approved source SHA is checked before Phase 1 outputs are read. The primary 1,144 accounts have source-reported inactivity of at least two years. Their two-fiscal-year eligibility remains unconfirmed. The 562 conflicts and 294 unknowns remain in reconciliation.""")
code("""recon = pd.read_csv(OUT / 'cohort_reconciliation.csv')
display(recon.groupby('scenario_cohort_status', as_index=False).size())
assert len(recon) == 2000 and recon.account_id.is_unique""")

md("""## 3. Synthetic event-history generation

Enrollment is synthetic t=0; one month is a continuous simulation unit. Exponential event times and independent censoring times are generated with seed 20261009. The model receives only the observed minimum and event flag; simulated truth is excluded from the fitting table.""")
code("""synthetic = generate_synthetic_cohort()
display(synthetic[['synthetic_subject_id','duration_months','event_observed',
                   'health_proxy','engagement_proxy','partner_proxy']].head())
display(pd.read_json(OUT / 'synthetic_generation_manifest.json', typ='series'))""")

md("""## 4. Kaplan–Meier estimate on synthetic subjects

The step curve is an empirical estimate within the synthetic experiment. Right-censored subjects contribute time at risk until their censoring point.""")
code("""km = pd.read_csv(OUT / 'synthetic_kaplan_meier.csv')
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.step(km.duration_months, km.survival_probability, where='post', color='#17324d')
ax.set(xlabel='Months since synthetic enrollment', ylabel='Survival probability',
       title='Synthetic methodology | Kaplan–Meier survival')
ax.set_ylim(0, 1.02)
fig.tight_layout(); fig.savefig(FIG / 'synthetic_kaplan_meier.png', dpi=160); plt.show(); plt.close(fig)""")

md("""## 5. Cox fit and hazard-ratio interpretation

Partial likelihood estimates relative hazard effects without specifying a baseline hazard. Lifelines' reported baseline survival is evaluated at its mean covariate profile, not at the all-zero profile. Absolute survival predictions use the fitted baseline survival. A hazard ratio of 1.5 means 1.5 times the instantaneous hazard, not 50% cumulative probability.""")
code("""model, coefficients, diagnostics, predictions = fit_synthetic_cox(synthetic)
display(coefficients[['covariate','true_generating_coefficient',
                      'estimated_log_hazard_coefficient','estimated_hazard_ratio',
                      'hazard_ratio_ci_lower_95','hazard_ratio_ci_upper_95']])
fig, ax = plt.subplots(figsize=(8, 4.5))
y = np.arange(len(coefficients))
hr = coefficients.estimated_hazard_ratio.to_numpy()
ax.errorbar(hr, y, xerr=[hr-coefficients.hazard_ratio_ci_lower_95.to_numpy(),
                         coefficients.hazard_ratio_ci_upper_95.to_numpy()-hr],
            fmt='o', color='#17324d', capsize=4)
ax.axvline(1, color='#a04c3b', linestyle='--')
ax.set(yticks=y, yticklabels=coefficients.covariate,
       xlabel='Estimated hazard ratio with 95% CI',
       title='Synthetic methodology | Cox hazard ratios')
fig.tight_layout(); fig.savefig(FIG / 'synthetic_hazard_ratios.png', dpi=160); plt.show(); plt.close(fig)""")

md("""## 6. Diagnostics and censoring

The rank-transformed Schoenfeld test checks time variation in fitted effects. A small p-value would be reported rather than silently selecting another seed. Concordance is shown separately for the fitting sample and an independent synthetic holdout; neither validates Everpure predictions.""")
code("""display(diagnostics)
assert diagnostics['n_events'] + diagnostics['n_right_censored'] == len(synthetic)""")

md("""## 7. Synthetic Cox survival curves

These absolute curves combine estimated relative effects with the synthetic baseline survival. Profiles are invented and are not Everpure accounts.""")
code("""pred = pd.read_csv(OUT / 'synthetic_survival_predictions.csv')
baseline_comparison = pd.DataFrame([{
    'synthetic_profile': 'lifelines mean covariates',
    'survival_at_36_months': diagnostics['baseline_survival_at_last_event']}, {
    'synthetic_profile': 'fitted all-zero covariates',
    'survival_at_36_months': pred.loc[(pred.synthetic_profile_id=='PROFILE_1') &
                                      (pred.horizon_months==36), 'survival_probability'].iloc[0]}, {
    'synthetic_profile': 'true generating all-zero',
    'survival_at_36_months': np.exp(-BASELINE_HAZARD*FOLLOWUP_MONTHS)}])
display(baseline_comparison)
fig, ax = plt.subplots(figsize=(8, 4.5))
for profile, group in pred.groupby('synthetic_profile_id'):
    ax.plot(group.horizon_months, group.survival_probability, marker='o', label=profile)
ax.set(xlabel='Months since synthetic enrollment', ylabel='Survival probability',
       title='Synthetic methodology | Cox survival profiles')
ax.set_ylim(0, 1.02); ax.legend()
fig.tight_layout(); fig.savefig(FIG / 'synthetic_cox_survival.png', dpi=160); plt.show(); plt.close(fig)""")

md("""## 8. Everpure assumed hazard parameters

The origin is the frozen 2026-10-09 analysis date, a modeling convention rather than an actual campaign start. The constant monthly baseline hazards and common feature effects below are chosen assumptions. They are independent of the synthetic Cox coefficients.""")
code("""assumptions = load_assumptions(ROOT)
display(assumptions)
accounts = load_phase1_accounts(ROOT)
features = engineer_features(accounts)
display(features[['health_unknown','partner_unknown','tickets_missing','ticket_sentinel']].sum())""")

md("""## 9. Account-level cumulative probabilities

For each account: P(T≤t)=1−exp[−baseline hazard × t × exp(assumed linear predictor)]. These are conditional scenario inputs, not fitted propensities.""")
code("""detail = pd.read_csv(OUT / 'reactivation_scenario_probabilities.csv')
effects = assumptions['assumed_log_hazard_effects']
hypothetical_eta = (effects['health_red'] + effects['partner_managed_yes'] +
                    effects['log1p_valid_tickets']*np.log1p(1) + effects['is_child'])
display(pd.DataFrame([{'profile': 'Hypothetical Red, managed, child, one valid ticket',
                       'base_12_month_assumed_probability': float(
                           exponential_event_probability(
                               assumptions['monthly_baseline_hazards']['base'], 12,
                               hypothetical_eta))}]))
curves = detail.groupby(['scenario_name','horizon_months'], as_index=False)[
    'cumulative_reactivation_probability'].mean()
fig, ax = plt.subplots(figsize=(8, 4.5))
for name, group in curves.groupby('scenario_name'):
    ax.plot(group.horizon_months, group.cumulative_reactivation_probability,
            marker='o', label=name.title())
ax.set(xlabel='Months from assumed 2026-10-09 origin',
       ylabel='Mean assumed cumulative probability',
       title='Everpure assumed scenarios | Mean probability, n=1,144')
ax.set_ylim(bottom=0); ax.legend()
fig.tight_layout(); fig.savefig(FIG / 'assumed_probability_curves.png', dpi=160); plt.show(); plt.close(fig)""")

md("""## 10. Expected reactivations

The expected count is the sum of account-level probabilities for the stated denominator. Linearity of expectation does not require independent accounts. These counts are not observed conversions, causal uplift, incremental revenue, or NPV.""")
code("""summary = pd.read_csv(OUT / 'reactivation_scenario_summary.csv')
display(summary[['scenario_name','horizon_months','cohort_accounts',
                 'expected_reactivations','mean_probability']])
wide = summary.pivot(index='horizon_months', columns='scenario_name',
                     values='expected_reactivations')
ax = wide[['conservative','base','optimistic']].plot.bar(figsize=(8, 4.5),
    color=['#8eabb8','#366784','#a04c3b'])
ax.set(xlabel='Horizon (months)', ylabel='Assumed expected reactivations',
       title='Everpure assumed scenarios | Expected count, n=1,144')
ax.legend(title='Scenario')
fig = ax.figure
fig.tight_layout(); fig.savefig(FIG / 'assumed_expected_counts.png', dpi=160); plt.show(); plt.close(fig)""")

md("""## 11. Assumption and cohort sensitivity

Hazard, effect, and missing-health choices keep the 1,144-account denominator fixed. The observed-average health effect weights the chosen Green/Yellow/Red contributions by their observed frequencies among known-health accounts in the primary cohort. Expanded cohorts hypothetically add the disputed and then unknown accounts, changing the denominator. Mean probability and expected count are shown together to distinguish propensity from population effects.""")
code("""sensitivity = pd.read_csv(OUT / 'scenario_sensitivity.csv')
s12 = sensitivity[sensitivity.horizon_months.eq(12)].sort_values('cohort_accounts')
labels = s12.sensitivity_case.str.replace('_', ' ', regex=False)
fig, axes = plt.subplots(1, 2, figsize=(14, 7))
axes[0].barh(labels, s12.mean_probability, color='#366784')
axes[0].set(xlabel='Mean assumed probability', title='Probability effect')
axes[1].barh(labels, s12.expected_reactivations, color='#a04c3b')
axes[1].set(xlabel='Expected count', title='Probability and denominator effects')
axes[1].set_xlim(0, s12.expected_reactivations.max()*1.20)
for y, n in enumerate(s12.cohort_accounts):
    axes[1].text(s12.expected_reactivations.iloc[y]+1, y, f'n={n:,}', va='center', fontsize=8)
fig.suptitle('Everpure assumed sensitivity | Base scenario, 12 months')
fig.tight_layout(); fig.savefig(FIG / 'assumed_sensitivity.png', dpi=160); plt.show(); plt.close(fig)
display(s12[['sensitivity_case','cohort_accounts','mean_probability','expected_reactivations']])""")

md("""## 12. Business interpretation and limits

All output applies to the supplied 2,000-row extract and the explicitly selected 1,144-account provisional cohort. True Everpure reactivation hazard, calibration, treatment effect, fiscal eligibility, and financial value are unidentified. Root-group dependence may affect total-count uncertainty, but no uncertainty interval is inferred from this extract.""")

md("""## 13. Phase 3 interface

`reactivation_scenario_probabilities.csv` is the only account-level probability input. Its versioned JSON contract states grain, provenance, source hash, horizon, cohort policy, and reconciliation. Phase 3 must supply separate financial assumptions and must not treat these assumed probabilities as observed conversion evidence.""")
code("""import json
contract = json.loads((OUT / 'phase3_input_contract.json').read_text(encoding='utf-8'))
display(contract)
assert contract['expected_rows'] == len(detail)
assert detail.probability_provenance.eq(contract['probability_provenance']).all()""")

for index, cell in enumerate(cells):
    cell.id = f"phase2-{index:02d}"
notebook = nbf.v4.new_notebook(cells=cells)
notebook.metadata = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
}
nbf.write(notebook, ROOT / "notebooks/02_survival_analysis.ipynb")
print(f"Built {len(cells)} Phase 2 notebook cells")
