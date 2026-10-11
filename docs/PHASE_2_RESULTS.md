# Phase 2 executed results

All figures below come from `outputs/phase2/` generated with Python 3.12, lifelines 0.30.3, and the frozen 2026-10-09 Phase 1 analysis date. The authoritative source SHA-256 is `6863ea0014f050355bf9e0c5166e2284edfe8521ea3d87a2a2fa168177a229bc`.

## Source and cohort

The supplied extract has 2,000 unique account IDs, 301 roots and 1,699 children; recorded historical spend sums to $2,541,024,291 and Phase 1 recorded 4,889 quality exception events. The source and Phase 1 artifacts remain unchanged. The primary **provisional** scenario cohort has 1,144 accounts with source-reported inactivity of at least two years. Reconciliation also retains 562 disagreements with the calendar proxy and 294 unknown reported-inactivity accounts. None of these counts confirms fiscal-year eligibility or complete install-base coverage.

## Synthetic methodology demonstration

With seed 20261009, 1,600 invented subjects generated 1,074 observed events and 526 right-censored records. Event fraction is 67.1% within this invented experiment; it says nothing about Everpure prevalence. The fitted estimates are:

| Synthetic covariate | Generating log coefficient | Fitted log coefficient | Fitted HR | 95% HR interval |
|---|---:|---:|---:|---:|
| health proxy | +0.450 | +0.505 | 1.658 | 1.470–1.869 |
| engagement proxy | -0.350 | -0.360 | 0.698 | 0.656–0.742 |
| partner proxy | +0.250 | +0.221 | 1.247 | 1.106–1.406 |

The in-sample concordance is 0.624 and independent synthetic holdout concordance is 0.595. Lifelines reported no fitting warnings; `fit_status=converged` follows the absence of convergence/numerical warnings and finite fitted estimates, rather than a hard-coded flag. Rank-transformed Schoenfeld p-values are 0.283, 0.252, and 0.939, respectively; none rejects at 0.05 in this single run. The baseline survival is monotone; its last fitted value is 0.1798 **at lifelines' mean covariate profile**. The fitted all-zero synthetic profile has 36-month survival 0.2846; the true generating all-zero survival is about 0.2837. These diagnostics and intervals describe only the synthetic experiment. They do not validate Everpure reactivation prediction.

## Assumed Everpure scenarios

The common assumed feature effects and monthly baselines are specified in [the versioned register](PHASE_2_ASSUMPTIONS.json). Primary probabilities range from approximately 0.0099 to 0.2433 across all accounts, scenarios, and horizons. The table sums account-level cumulative probabilities; its denominator is 1,144 in each cell.

| Scenario | 3 months | 6 months | 12 months |
|---|---:|---:|---:|
| Conservative | 16.965 | 33.672 | 66.330 |
| Base | 33.672 | 66.330 | 128.724 |
| Optimistic | 55.555 | 108.348 | 206.205 |

These are **conditional expected reactivation counts**, not observed conversions, causal uplift, incremental bookings, recoverable revenue, or NPV. The 12-month base mean account probability is 0.1125, with account-level range 0.0765–0.1541. No confidence interval is attached to the assumed business probabilities.

## Sensitivity

At 12 months in the base scenario, halving the baseline hazard lowers the primary expected count from 128.724 to 66.330; multiplying it by 1.5 raises the count to 187.422. Holding the hazard fixed and halving the assumed covariate effects raises the count to 140.197; multiplying those effects by 1.5 lowers it to 118.768. Across 3, 6, and 12 months at the base parameters, the same 1,144 accounts yield 33.672, 66.330, and 128.724 expected events. These changes are probability effects at a fixed denominator.

Hypothetically including the 562 disputed accounts yields 1,706 accounts and 191.884 expected events at 12 months, with mean probability 0.11248. Including all 294 unknowns as well yields 2,000 accounts and 225.180 expected events, with mean probability 0.11259. The larger counts primarily reflect larger denominators; neither policy establishes operational eligibility.

For the unchanged 1,144-account primary cohort, 12-month base expected reactivations are **128.724** under the reference-level missing-health contribution, **121.091** if unknown health receives the Yellow effect, and **112.374** if it receives the Red effect. Weighting the chosen Green/Yellow/Red effects by observed frequencies among known-health primary-cohort accounts gives a log effect of **-0.167391** and expected count **120.269**. The independent audit's approximate 121.349 for an “observed-average effect” does not match this explicitly defined weighting rule; no value was inserted to force agreement. All four counts are computed by the same model, and the primary account export remains unchanged.

## Limits and handoff

True Everpure reactivation hazards, fitted Cox effects, real baseline survival, fiscal-year eligibility, calibration, campaign treatment effects, out-of-sample real predictive performance, incremental revenue, and NPV remain unidentified. Phase 3 may consume `reactivation_scenario_probabilities.csv` only as a versioned assumed-probability input under [the contract](PHASE_2_DATA_CONTRACT.md). It must supply separate commercial and financial assumptions.
