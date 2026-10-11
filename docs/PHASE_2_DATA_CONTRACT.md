# Phase 2 to Phase 3 probability input contract

The machine-readable contract is `outputs/phase2/phase3_input_contract.json`, version `phase2-to-phase3-v2`. The permitted account-level input is the **local, Git-ignored** `outputs/phase2/reactivation_scenario_probabilities.csv`; `reactivation_scenario_summary.csv`, `assumptions.json`, the local Git-ignored `cohort_reconciliation.csv`, and `manifest.json` support validation and interpretation. The synthetic files are methodology evidence only. Phase 3 consumption should call `validate_phase3_artifacts(output_dir)` before using the files.

| Field | Contract |
|---|---|
| `account_id` | Unique observed source account key within scenario × horizon; no synthetic ID |
| `root_account_id` | Phase 1 resolved root key; account grain remains one account |
| `scenario_cohort_status` | `primary_reported_2y`; provisional source-reported two-year policy |
| `analysis_as_of_date` | `2026-10-09`, assumed prediction origin |
| `scenario_name` | `conservative`, `base`, or `optimistic` |
| `horizon_months` | 3, 6, or 12 continuous months |
| `assumed_baseline_hazard_per_month` | Constant assumed monthly scenario hazard |
| `assumed_log_hazard_linear_predictor` | Assumed feature contribution for the account |
| `cumulative_reactivation_probability` | Assumed `P(T <= horizon)` from origin; finite in [0,1] |
| `scenario_parameter_version` | `phase2-assumptions-v1` |
| `probability_provenance` | `ASSUMPTION_BASED_NOT_CALIBRATED` |
| `source_baseline_sha` | `6863ea0014f050355bf9e0c5166e2284edfe8521ea3d87a2a2fa168177a229bc` |
| `cohort_policy` | `reported_2y_scenario_cohort` in the primary export |
| Missingness flags | `health_unknown`, `partner_unknown`, `tickets_missing`, `ticket_sentinel` |

The expected grain is exactly 1,144 accounts × 3 scenarios × 3 horizons = **10,296 rows** with unique `(account_id, scenario_name, horizon_months)`. Each scenario/horizon subset has 1,144 rows. All account-level probabilities must be in [0,1], nondecreasing with horizon, and ordered conservative ≤ base ≤ optimistic for each account/horizon. `reactivation_scenario_summary.csv` must equal the sum and mean of the corresponding detailed probabilities, with the same scenario and horizon. The file manifest supplies SHA-256 identities and provenance. The 2,000-row reconciliation establishes the denominator policy and retains the 562 conflicts and 294 unknowns.

## Required simulation semantics

The 3-, 6-, and 12-month values are **cumulative probabilities of one first reactivation**. Never add cumulative expected counts across horizons. Never sample each cumulative horizon independently; that can imply a reactivation by 3 months but no reactivation by 6 months. An account can experience at most one first-reactivation event in a simulation path. A coherent first-event time can be sampled from its assumed constant hazard, with all horizon indicators derived from that same time.

Conservative, base, and optimistic are fixed assumed cases. They are neither mutually exclusive observed outcomes nor confidence intervals, and no empirical probability weights exist. Phase 3 must not randomly choose a case unless new explicit weights are separately supplied and approved.

No observed treatment assignment or untreated counterfactual exists. Gross assumed reactivation is **not** incremental campaign-attributable uplift. Without a separately assumed counterfactual, any valuation must be labeled **illustrative gross reactivation economics**. Incremental cash flow requires additional assumptions.

Accounts under one root may have correlated outcomes. Phase 3 must document its dependence assumption for any simulated total or interval. Parent and child historical spend cannot automatically be summed into financial recovery.

## Parameter and time identity

The contract records `assumption_fingerprint_sha256`: SHA-256 of the **complete** assumption register serialized as UTF-8 JSON with sorted keys, compact separators, `ensure_ascii=False`, and no NaN. This binds actual values and explanatory content, not just the static `phase2-assumptions-v1` label. It also records hashes of the probability and summary CSVs. Recompute all three hashes and validate the schema, values, scenario baselines, probability formula, and reconciliation before consumption. Regenerating the contract from changed assumption content changes the fingerprint; a stale contract fails validation.

The probability model's month is a continuous model-time unit. Three, six, and 12 units do **not** become exact calendar deadlines without an explicit calendar mapping. Phase 3 must separately specify any calendar-date mapping and financial discounting convention.

Phase 3 may use these probabilities only as **assumed** event-probability inputs. It must not relabel them as calibrated Everpure propensities, treat expected reactivations as observed conversions or causal campaign uplift, equate historical recorded spend with recoverable annual revenue, add parent and child spend without an accounting rule, infer a discount-response effect, or present scenario spread as a statistical confidence interval. Synthetic coefficients and subjects may not be used as customer evidence.

Before the separate Phase 3 financial model, obtain margin, incremental revenue definition, revenue recognition period, parent-child consolidation convention, campaign costs, discount-policy assumptions, financial discount rate, renewal/retention horizon, uncertainty distributions, and a Monte Carlo seed and run count. The 1,000-run simulation and NPV analysis belong to Phase 3 and are absent here.
