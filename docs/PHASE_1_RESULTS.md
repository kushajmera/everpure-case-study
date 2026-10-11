# Phase 1 observed findings

All figures are calculated from the unchanged CSV with an analysis date of **2026-10-09**. The detailed `outputs/phase1/metrics.json` and executed notebook are retained locally and regenerated from the separately supplied source; they are excluded from Git because they contain reconstructable source diagnostics or account-level displays.

## Reconciliation

The source has **2,000 rows and 2,000 unique accounts**. The original recorded historical spend sums to **$2,541,024,291**. All 2,000 rows resolve to one of **301 root accounts**: 301 roots and 1,699 direct children. The hierarchy reaches depth one in this file. Summing once per account yields the same **$2,541,024,291** across root groups; account-native region SQL also reconciles to that total. No recorded spend was excluded by hierarchy resolution.

## Eligibility conflict

The latest booking date is **2024-06-22**. With the two-calendar-year cutoff of **2024-10-09**, all **2,000** rows meet the date proxy. In contrast, source-reported `years_inactive` marks **1,144** at least two years, **562** below two years, and **294** unknown. The explicit comparison statuses are **1,144 `agree_eligible`, 562 `disagree`, 294 `unknown`, and zero `agree_ineligible`**. A broader **1,546** known rows have a reported versus date-derived inactivity gap of at least six months. The 562 eligibility-conflicting account rows represent **$717,948,793** of recorded historical spend; the 294 unknown rows represent **$355,060,992**. Neither amount is forecast recovery. Fiscal-year eligibility remains unverified.

The calendar proxy is analysis-date sensitive: **1,269** eligible at 2024-06-22, **1,634** at 2025-06-22, and **2,000** at both 2026-06-22 and the configured 2026-10-09. The source-reported inactivity measurement date is unknown, and two fiscal years need not equal a rolling two-calendar-year cutoff.

## Descriptive commercial exposure

France's normalized **667 account rows** hold **$845,049,984** of account-native recorded spend (**33.3%**); it also represents **33.35%** of account rows. The other region spend shares are US West **18.2%**, Japan **17.7%**, US East **15.9%**, and Germany **15.0%**. The largest root contains 11 account rows. The top 10 roots account for **6.9%** of the source spend total; the top 30 account for **18.2%**. Root group size and additive spend have a **0.881** Pearson correlation in this file, so larger groups naturally rise in total-spend rankings. Root count and mean recorded spend per account are included as descriptive size controls in the local-only root tables. None of these values establishes economic attractiveness or expected recoverable revenue.

**236 of 301** root groups contain conflicting known partner flags, **269** contain at least one unresolved partner flag, and **294** span more than one account-native region. Review ownership and group metadata before any parent-level commercial assignment. Mixed child metadata can be legitimate and is not silently overwritten by a root value.

## Source caveat

Booking dates follow an exact account-ID sequence, and contract start is exactly 365 days earlier. Consequently, within-root booking-date ranks and gaps collapse to account-ID arithmetic. The executed `LAG`/`LEAD` output is retained locally as a **synthetic-date/source-pattern diagnostic**, not behavioral booking evidence. Recorded spend has no declared historical period. For **291 of 298** referenced parents, the parent's own recorded spend is below the sum of direct-child recorded spend; that is evidence against a simple “parent fully includes every child” interpretation, but it does not reveal the actual accounting convention. Additive source-row spend is not verified consolidated revenue. There is no basis here to infer real revenue decay velocity, reactivation probabilities, annual recurring revenue, ticket velocity, or incremental recovery. The separate [synthetic SQL demonstration](SYNTHETIC_REVENUE_DEMO.md) illustrates decay calculations without changing these source-derived results.
