# Phase 2 assumption and identifiability register

The authoritative machine-readable parameter source is [PHASE_2_ASSUMPTIONS.json](PHASE_2_ASSUMPTIONS.json), version `phase2-assumptions-v1`. Every account probability and sensitivity result has provenance `ASSUMPTION_BASED_NOT_CALIBRATED`. No parameter was estimated from Everpure reactivation outcomes, and the synthetic Cox fit did not initialize any business parameter.

| Quantity | Value or rule | Status and reason |
|---|---|---|
| Source account ID, reported inactivity, health, ownership, tickets, parent ID | Unchanged source fields | `OBSERVED_SOURCE`; field timing and meaning remain source-limited |
| Clean health/ownership, valid tickets, root mapping, provisional cohort | Phase 1 deterministic rules | `DERIVED_SOURCE`; not event labels or confirmed fiscal eligibility |
| Synthetic hazard and generating effects | 0.035/month; +0.45, -0.35, +0.25 | `SYNTHETIC_METHODOLOGY`; invented to exercise Cox fitting |
| Synthetic fitted effects, baseline, diagnostics | Lifelines output on generated event histories | `SYNTHETIC_METHODOLOGY`; not transportable Everpure estimates |
| Prediction origin | 2026-10-09 | `ASSUMPTION_BASED_NOT_CALIBRATED`; frozen analysis date, no observed campaign start |
| Conservative/base/optimistic baselines | 0.006 / 0.012 / 0.020 per continuous month | `ASSUMPTION_BASED_NOT_CALIBRATED`; transparent spread, no external benchmark claimed |
| Health Red / Yellow effects | -0.35 / -0.15 | `ASSUMPTION_BASED_NOT_CALIBRATED`; illustrative directions only |
| Partner-managed effect | +0.15 | `ASSUMPTION_BASED_NOT_CALIBRATED`; not a causal channel effect |
| Log(1+valid tickets) effect | -0.08 | `ASSUMPTION_BASED_NOT_CALIBRATED`; no ticket timestamps |
| Child effect | -0.10 | `ASSUMPTION_BASED_NOT_CALIBRATED`; no independence or parent consolidation inference |
| Missing health, ownership, tickets | Flags retained; Green, direct, and zero-ticket reference contributions respectively | Reference-level assumed contribution with explicit missingness flags; no source-data correction or observed effect |
| Horizons | 3, 6, 12 continuous months | Chosen forecast durations, not observed follow-up |
| Primary cohort | 1,144 source-reported >=2-year accounts | Provisional inclusion policy, not confirmed two-fiscal-year eligibility |
| Expanded cohorts | 1,706 including conflicts; 2,000 including unknowns | Hypothetical population sensitivity only |

The illustrative baselines are ordered and all scenarios share the same feature effects, guaranteeing pointwise ordering. `scenario_sensitivity.csv` varies the base hazard by 0.5 and 1.5, scales assumed covariate effects by 0, 0.5, and 1.5, compares 3/6/12-month horizons, separately changes the included population, and scores missing health as Yellow, Red, or an observed-frequency weighted average of the **chosen** health effects among known-health primary-cohort accounts. The primary result is never overwritten. Differences between scenarios are **assumption sensitivity**, not statistical confidence intervals.

## What the source cannot identify

| Quantity | Why unidentified | Additional evidence needed |
|---|---|---|
| True reactivation hazard and real baseline survival | No observed reactivation event time or risk-set follow-up | Timestamped enrollment/prediction origin, event date, censoring date for each account |
| Everpure Cox effects | No observed time-to-event response | Longitudinal event/censor records plus covariates measured before event and sufficient events |
| Fiscal eligibility | Fiscal-year boundary and rule interpretation absent | Approved fiscal calendar, two-year policy definition, trusted booking-date provenance |
| Campaign treatment effect | No treated/control assignment or outcomes | Intervention and comparable control histories with a causal identification design |
| Calibration and real predictive performance | No held-out real event outcomes | Independent historical validation window with complete event and censoring ascertainment |
| Incremental revenue and NPV | Spend period, consolidation, margins, costs, discounts, and retention absent | Approved financial inputs and account-period incremental cash-flow data |

Empirical estimation would require a defined at-risk dormant cohort; account and root IDs; dated origin, reactivation event, and last-observed/censoring endpoint; covariates timestamped before the origin; complete follow-up or a documented censoring mechanism; and enough events to support model diagnostics and held-out calibration. The source's deterministic booking dates cannot supply those records. Parent-group dependence should be addressed in eventual uncertainty analysis, for example by group-aware validation or clustered uncertainty methods, only after real histories exist.
