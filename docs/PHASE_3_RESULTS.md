# Phase 3 illustrative financial results

**Verdict: the model executes and reconciles under its declared assumptions.** These are conditional financial scenario outputs, not observed Everpure revenue, a calibrated forecast, an empirically optimal price offer, or causal campaign uplift. Population: 1,144 provisional source-reported two-year inactive accounts. Currency: USD. The analyst-selected unit economics are $1,000 gross per paid service month, 60% contribution margin, $100 outreach per target, $200 per first reactivation, and a 12% annual effective financial discount rate over 12 continuous model months. Every cell has 1,000 independent replications, paired across hazard and commercial-offer scenarios by common random numbers.

## Nine-cell outcome distribution

Values below are dollars except counts and loss probability. P5/P95 are **conditional simulated outcome percentiles**, not confidence intervals for real program value. Gross revenue, price deduction, contribution, outreach and activation columns are **nominal mean totals**; NPV is a discounted net amount. Do not add nominal columns to recreate NPV. The present-value bridge is in `monthly_cashflow_summary.csv`.

| Hazard | Offer | Mean NPV | Median | P5 | P95 | Pr(NPV<0) | Mean events | Mean billed accounts | Gross revenue | Price deduction | Contribution | Outreach | Activation |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Conservative | 5% | 68,469 | 67,714 | 24,277 | 113,356 | 0.3% | 66.761 | 61.384 | 372,045 | 18,602 | 212,066 | 114,400 | 13,352 |
| Conservative | 15% | 47,890 | 47,201 | 8,517 | 87,927 | 2.4% | 66.761 | 61.384 | 372,045 | 55,807 | 189,743 | 114,400 | 13,352 |
| Conservative | 30% | 17,021 | 16,435 | −15,070 | 49,499 | 18.1% | 66.761 | 61.384 | 372,045 | 111,614 | 156,259 | 114,400 | 13,352 |
| Base | 5% | 243,113 | 242,669 | 184,510 | 303,489 | 0% | 128.836 | 118.749 | 726,614 | 36,331 | 414,170 | 114,400 | 25,767 |
| Base | 15% | 202,912 | 202,618 | 150,709 | 256,482 | 0% | 128.836 | 118.749 | 726,614 | 108,992 | 370,573 | 114,400 | 25,767 |
| Base | 30% | 142,612 | 142,500 | 99,966 | 186,059 | 0% | 128.836 | 118.749 | 726,614 | 217,984 | 305,178 | 114,400 | 25,767 |
| Optimistic | 5% | 465,794 | 465,537 | 395,658 | 541,226 | 0% | 206.125 | 190.728 | 1,177,933 | 58,897 | 671,422 | 114,400 | 41,225 |
| Optimistic | 15% | 400,610 | 400,458 | 338,091 | 467,804 | 0% | 206.125 | 190.728 | 1,177,933 | 176,690 | 600,746 | 114,400 | 41,225 |
| Optimistic | 30% | 302,834 | 302,625 | 251,721 | 357,269 | 0% | 206.125 | 190.728 | 1,177,933 | 353,380 | 494,732 | 114,400 | 41,225 |

The optimistic/5% P95 is **$541,226.198208**, rounded to **$541,226** to the nearest dollar. The lower price discount mechanically gives more contribution because **reactivation hazards are held fixed across offers**. This does not establish what customers would do at those prices. A zero simulated loss frequency in 1,000 runs is not proof of zero true risk, especially with unestimated financial parameters and root dependence.

## Independent expected-value audit

The closed-form expected NPV uses the same monthly billing cutoff and continuous activation-cost discounting, but no sampled event times. The maximum absolute standardized Monte Carlo discrepancy is **1.885**, below the predeclared 4.5 nine-cell diagnostic.

| Hazard | Offer | Analytical expected NPV | Monte Carlo mean | MC standard error | Standardized discrepancy |
|---|---|---:|---:|---:|---:|
| Conservative | 5% | 66,866 | 68,469 | 851 | 1.885 |
| Conservative | 15% | 46,465 | 47,890 | 757 | 1.884 |
| Conservative | 30% | 15,862 | 17,021 | 616 | 1.881 |
| Base | 5% | 241,533 | 243,113 | 1,152 | 1.371 |
| Base | 15% | 201,502 | 202,912 | 1,025 | 1.376 |
| Base | 30% | 141,454 | 142,612 | 835 | 1.386 |
| Optimistic | 5% | 464,631 | 465,794 | 1,403 | 0.829 |
| Optimistic | 15% | 399,568 | 400,610 | 1,249 | 0.834 |
| Optimistic | 30% | 301,974 | 302,834 | 1,018 | 0.845 |

Phase 2 analytical first-event expectations by month 3 / 6 / 12 reconcile to conservative 16.965 / 33.672 / 66.330, base 33.672 / 66.330 / 128.724, and optimistic 55.555 / 108.348 / 206.205. These are cumulative expected counts, so the three horizon columns must not be added.

## Financial sensitivity and break-even

For the base hazard and 15% offer, analytical expected NPV is **$201,502**. One-at-a-time changes produce:

| Assumption change | Expected NPV change |
|---|---:|
| Monthly gross revenue $750 / $1,250 | −$85,067 / +$85,067 |
| Contribution margin 45% / 75% | −$85,067 / +$85,067 |
| Outreach cost $50 / $150 | +$57,200 / −$57,200 |
| Activation cost $100 / $300 | +$12,184 / −$12,184 |
| Financial rate 0% / 24% | +$27,397 / −$22,595 |
| Customer price discount 5% / 30% | +$40,032 / −$60,048 |
| Hazard multiplier 0.5 / 1.5 | −$155,037 / +$149,451 |
| Retention cap 3 / 6 paid months | −$185,652 / −$77,387 |

A **combined hypothetical adverse stress** sets monthly gross revenue to $750, margin to 45%, outreach to $150, activation to $300, annual financial rate to 24%, and retention to at most three paid months, while retaining base hazards and the 15% offer. The independent analytical calculation is **−$124,647.43**. This is close to the audit's approximately −$124,704 stress indication, but its exact assumption vector was not supplied; the documented calculation is the reproducible value. It does not alter the primary nine-cell simulation.

At the base hazard and 5% offer, the analytical zero-NPV thresholds are **$364.89 monthly gross revenue**, **21.89% margin**, **$311.13 maximum outreach per target**, and **$2,182.41 maximum activation per event**. The 15% and 30% offers would hypothetically need **1.132×** and **1.412×** each account's hazard, respectively, to match the 5% offer's expected NPV. These multipliers are solutions to a hypothetical response mechanism, not measured price effects.

## Integrity, outputs and limits

The unchanged source SHA-256 is `6863ea0014f050355bf9e0c5166e2284edfe8521ea3d87a2a2fa168177a229bc`; the Phase 2 probability CSV SHA-256 is `6322a0adc58dbaa999e5523f3a17db5faaa61ca3f8a359011a6322e0466800c8`. The Phase 3 assumption fingerprint is `b953c02d3fdcfacc62d9e6755889040e9f8bd12db7c830a88c79f5c991267e70`. The pipeline writes 9,000 run records, 9 summary rows, month-zero through month-12 cash-flow summaries, analytical sensitivities and thresholds, a financial reconciliation file, machine-readable handoff contract and hash manifest. The 10,296-row account economic table stays local and Git-ignored. The notebook produces six aggregate charts and displays no real account IDs.

For base hazards and a 15% offer, **96.8%** of analytical expected portfolio NPV comes from root groups containing more than one modeled account (257 of 295 modeled root groups). That is a concentration and possible overlap warning. The source does not establish whether independently assumed billable opportunities for parents and children economically overlap, so this is not proof of double counting.

Manifest hashes establish file consistency, the account bridge establishes arithmetic coherence, and the fresh closed-form oracle independently checks expected financial values from the assumed hazards and cash-flow rules. None validates the analyst-selected financial inputs against realized outcomes. The original assessment page 2 requires 1,000 Monte Carlo runs and three discount scenarios but does not prescribe the numerical financial assumptions or offer percentages. Its existing source `discount_tier_pct` values span 5%–65% and average about 34.9% in the provisional cohort; those values were not used to infer offer response.

The source's spend period, consolidation semantics, fiscal eligibility, treatment response, customer revenue, margin and retention remain unresolved. The simulation is numerically reproducible under assumptions, not validated against realized commercial outcomes.
