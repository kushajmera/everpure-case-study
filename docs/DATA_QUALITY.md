# Data-quality findings

Analysis date: **2026-10-09**. All counts below come from the supplied source and `outputs/phase1/metrics.json`, not from the case prompt's reference table.

| Check | Actual finding | Handling |
|---|---:|---|
| Source rows / unique account IDs | 2,000 / 2,000 | All retained; no actual duplicate ID rows. |
| Root rows / child rows | 301 / 1,699 | All child references valid. |
| Unresolved hierarchy rows | 0 | Resolver still flags missing, duplicate, self-referential, and cyclic paths. |
| Raw region variants / canonical regions | 6 / 5 | 667 France rows normalized; source labels retained. |
| Unknown SFDC health | 844 | 444 literal `nan`, 400 literal `Missing`; no imputation. |
| Unresolved partner ownership | 654 | Empty source values preserved as unknown. |
| Ticket sentinel 999 / genuine zero | 322 / 324 | Sentinel omitted from valid ticket statistics; zeros retained. |
| Missing reported years inactive | 294 | Left unknown under source-reported rule. |
| Source-reported under two years | 562 | Contradicts date proxy for all 562. |
| At least six-month reported/date-derived value gap | 1,546 | Flagged for review; this is broader than eligibility disagreement. |
| Source-reported at least two years | 1,144 | Kept separate from calendar proxy. |
| Calendar two-year proxy eligible | 2,000 | All booking dates precede 2024-10-09. Not confirmed fiscal eligibility. |
| Quality exception rows / affected accounts | 4,889 / 1,968 | Includes informational region normalization and multiple exceptions per account. |
| Eligibility comparison status | 1,144 agree eligible / 562 disagree / 294 unknown | There are zero agree-ineligible accounts at this default as-of date. `eligibility_disagrees=False` is not proof of agreement. |

The brief describes injected duplicate account records. The actual file has **zero duplicate account IDs**. We implemented duplicate detection without inventing a deduplication action.

Booking dates run **2019-01-01 to 2024-06-22** and increase perfectly with numeric account ID. Contract dates run **2018-01-01 to 2023-06-23**, always exactly **365 days earlier**. Within-root booking-date ranks therefore reverse numeric ID ranks, and SQL adjacent-date gaps equal numeric ID differences. The account-level [window_analytics.csv](../outputs/phase1/window_analytics.csv) remains local as a **synthetic-date/source-pattern diagnostic**, not an independent customer-behavior or booking-frequency measure. The pattern does not establish which source dates, if any, should replace those supplied.

The exception register now separates actual `cleaned_value` from `comparison_value`: the latter holds the calendar-derived reference for inactivity discrepancies, while `years_inactive` remains as reported. Non-finite numeric strings are flagged explicitly. There were no such non-finite values in the original numeric fields. A missing discount is a missing-value issue only, not simultaneously an invalid-range issue.

The [date-sensitivity table](../outputs/phase1/analysis_date_sensitivity.csv) gives **1,269**, **1,634**, **2,000**, and **2,000** calendar-proxy eligible rows at 2024-06-22, 2025-06-22, 2026-06-22, and 2026-10-09 respectively. The source-reported inactivity field may have been measured at an unknown earlier snapshot. Its provenance is needed before the definitions can be reconciled. The brief's “over 50% of the install base” cannot be verified from this extract without the full install-base denominator and fiscal-year definition.

The CSV's 0.05–0.65 discount values are consistent with fraction-encoded percentages (5%–65%); this is a scale interpretation for validation, not evidence of discount policy or an approved scenario range. No negative spend, out-of-range discounts, invalid dates, or 999-as-zero conversions were found.
