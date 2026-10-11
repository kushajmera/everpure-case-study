# Phase 3 financial assumption and identifiability register

The authoritative machine-readable values are in [`PHASE_3_FINANCIAL_ASSUMPTIONS.json`](PHASE_3_FINANCIAL_ASSUMPTIONS.json). Its fingerprint is SHA-256 of sorted-key, compact UTF-8 JSON with no NaN, excluding only the stored `fingerprint_sha256` field to avoid circular hashing. Current fingerprint: `b953c02d3fdcfacc62d9e6755889040e9f8bd12db7c830a88c79f5c991267e70`.

| Input or rule | Primary value | Evidence status and material effect |
|---|---:|---|
| Baseline event hazards | 0.006 / 0.012 / 0.020 monthly | Frozen Phase 2 **assumptions**, no observed reactivation calibration |
| Account relative hazard effects | Frozen Phase 2 coefficients | Assumed effects of health, ownership, tickets and hierarchy; missing values score at reference level with flags |
| Monthly gross revenue after event | $1,000 | Analyst-selected, independent of recorded historical spend; drives value linearly |
| Contribution margin | 60% | Analyst-selected; includes ongoing servicing costs |
| Outreach per targeted account | $100 at month zero | Analyst-selected; applies to all 1,144 targets |
| Activation per first event | $200 at exact event time through month 12 | Analyst-selected; one payment per event |
| Annual effective financial discount rate | 12% | Analyst-selected present-value rate; $DF(t)=(1.12)^{-t/12}$ |
| Commercial price discounts | 5%, 15%, 30% | Analyst-selected hypothetical offers; not the source `discount_tier_pct`; no modeled response |
| Horizon | 12 continuous model months | Origin 2026-10-09 is a convention, not observed launch |
| Billing | Full service month when $T\le m-1$; collect at $m$ | No proration; event through month 12 may lack paid service month |
| Retention | Through modeled horizon | No churn in primary model; capped 3 and 6 paid months shown separately |
| Replications | 1,000 per each of nine cells | The assessment explicitly requires a 1,000-run Monte Carlo; conditional event randomness only, not parameter uncertainty |
| Generator | NumPy PCG64, seed 20261009 | Sorted account/root ordering and common random numbers |
| Within-root dependence | Conditional independence | Root correlation is unidentified; downside ranges depend on it |
| Untreated counterfactual | None | Program NPV cannot be called incremental campaign uplift |

The original `CandidateAssessmentPackageEverpure.pdf` was located outside the repository and page 2 was verified. It calls for a 1,000-run Monte Carlo NPV projection under varying discount tiers and a three-tier financial summary. It prescribes no revenue, margin, campaign cost, financial discount rate, horizon, or offer percentages. Those financial inputs are analyst-selected illustrative defaults from the implementation prompt.

The observed source field `discount_tier_pct` spans **5%–65%** across the 2,000-row extract. Its mean in the 1,144-account provisional primary cohort is **34.8584%**, about 34.9% (observed field; source-derived cohort mean). It is an existing account attribute. It is neither a proposed new offer nor evidence that a price change causes reactivation. The 5%/15%/30% scenario offers are separate analyst-selected interventions, and no discount-response model is fitted.

The input contains 562 source/date eligibility conflicts and 294 unknown records; fiscal-year eligibility is unconfirmed even for the 1,144 modeled rows. Unknown health, partner ownership and valid ticket counts remain flagged in the confidential handoff. Uncertainty in revenue, margins, retention, treatment response, and group dependence is **not estimated** from this source. Sensitivity ranges are assumptions, not empirical confidence intervals.

The separate `combined_adverse_hypothetical` sensitivity in `outputs/phase3/financial_sensitivity.csv` jointly changes revenue to $750, margin to 45%, outreach to $150, activation to $300, the annual financial rate to 24%, and retention to three paid months. It retains base hazards and the 15% offer. It is explicitly outside the approved primary assumptions and produces analytical expected NPV of approximately −$124,647. The original audit's approximate −$124,704 indication did not include a reproducible parameter vector.
