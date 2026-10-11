# Data dictionary

## Source grain

One CSV row per `account_id` in this file. `source_row_number` is the original 1-based CSV line number (header is line 1). All 12 source columns are retained as exact strings in `cleaned_accounts.csv`; derived columns are appended. No rows are dropped.

| Raw field | Observed representation | Interpretation / caution |
|---|---|---|
| `account_id` | `ACC_...` string | Account key. Exactly unique in supplied file. |
| `parent_account_id` | Account ID or empty string | Empty means root; every nonempty reference resolves in this file. |
| `region` | Six text variants | Source label; France differs in case and trailing space. |
| `last_booking_date` | `YYYY-MM-DD` | Last booking date as supplied; artificial sequence warning applies. |
| `contract_start_date` | `YYYY-MM-DD` | Supplied contract start; always 365 days before booking in this file. |
| `years_inactive` | Decimal or empty string | Source-reported inactivity; measurement date and derivation are unspecified. |
| `historical_spend_usd` | Integer-like USD value | Period and parent consolidation unknown; neither ARR nor recoverable revenue. |
| `discount_tier_pct` | Decimal 0.05–0.65 | Stored as a fraction (e.g. 0.25 = 25%) for range validation. Commercial application is unverified. |
| `sfdc_health_score` | Green, Yellow, Red, `Missing`, `nan` | The last two literal strings represent unknown health. |
| `partner_managed` | `1.0`, `0.0`, empty | Three states: yes, no, unresolved. |
| `open_support_tickets` | 0, 1, 2, 3, 5, 999 | 999 is an error sentinel; zero is a valid count. No ticket timestamps. |
| `monthly_usage_gb` | Integer-like GB | Source monthly usage measure; month and measurement window unspecified. |

## Main derived fields

| Field | Rule |
|---|---|
| `account_id_key`, `parent_account_id_key` | Trimmed keys used for integrity checks; raw strings remain available. |
| `region_clean` | Whitespace normalized and case-insensitive lookup: `amer - us east` → `AMER - US East`, `amer - us west` → `AMER - US West`, `apac - japan` → `APAC - Japan`, `emea - france` → `EMEA - France`, `emea - germany` → `EMEA - Germany`. Unknown labels remain null. |
| `*_parsed` | Strict `YYYY-MM-DD` datetime parsing, with invalid values flagged. |
| `*_num` | Numeric interpretation; invalid values flagged. |
| `health_clean` | Green, Yellow, or Red; anything else unknown. |
| `partner_managed_clean` | 1, 0, or null. |
| `tickets_clean`, `ticket_sentinel` | 999 becomes null in the analytical count and is separately flagged. |
| `calendar_inactive_days` | Analysis date minus last booking date in days. |
| `calendar_inactive_years_approx` | Days divided by 365.2425; display only, not the eligibility rule. |
| `inactivity_year_gap_approx`, `inactivity_value_mismatch` | Date-derived approximate years minus source-reported years; absolute gap of at least 0.5 years is flagged for review. |
| `calendar_2y_proxy_eligible` | Booking date on or before analysis date minus two calendar years. |
| `reported_2y_eligible` | `years_inactive >= 2`; null remains unknown. |
| `eligibility_comparison_status` | `agree_eligible`, `agree_ineligible`, `disagree`, or `unknown`; unknown if either input is missing. The real file has 1,144, 0, 562, and 294 rows respectively. |
| `eligibility_disagrees` | True only for **confirmed** disagreements. False also includes unknown comparisons; it is not evidence of agreement or routing readiness. Use `eligibility_comparison_status` downstream. |
| `root_account_id`, `hierarchy_depth`, `hierarchy_status` | Traversal of source parent links; unresolved paths are explicit. |
| `additive_recorded_spend_usd` | Sum of once-per-account source spend within a resolved root group. It is **not** verified consolidated revenue. |

The `data_quality_exceptions.csv` register has `source_row_number`, `account_id`, `field`, `raw_value`, `cleaned_value`, `comparison_value`, `issue_code`, `severity`, and `resolution`. `cleaned_value` is populated only when the field was actually normalized or replaced, such as region formatting. For `INACTIVITY_VALUE_GAP_6M` and `INACTIVITY_CONTRADICTION`, it stays empty; `comparison_value` holds independently calculated calendar inactivity, while source `years_inactive` remains unchanged. A single account can have multiple rows. `auto_resolved` means a deterministic formatting normalization; `left_unknown` means no imputation; `manual_review` means source or business owner clarification is needed. `NON_FINITE_NUMBER` covers literal `nan`, `inf`, and `-inf` in numeric fields; those analytical numeric values become null and the raw strings remain visible.

`account_quality_summary.csv` has one row per source account with exception counts by resolution and `has_manual_review_exceptions`. The older `needs_manual_review` field remains as an identical compatibility alias. These are **quality-triage indicators, not GTM readiness gates**: no manual-review issue does not mean all fields are known, fiscal eligibility is confirmed, or outreach is authorized.

`direct_child_counts.csv` counts each immediate parent reference, independent of depth. `parent_spend_summary.csv` groups all descendants under a resolved root and separately counts direct root children.

`parent_child_spend_comparison.csv` compares each referenced parent's own recorded spend with the sum of its direct children's recorded spend. It is evidence about a *simple full-child-inclusion hypothesis*, not a consolidation adjustment. `analysis_date_sensitivity.csv` reapplies the same two-calendar-year proxy at four explicitly labeled dates. `mean_recorded_spend_per_account_usd` in root and regional summaries is a size control, not a predictive score.

Synthetic input provenance comes from the isolated `data/synthetic/` directory, its README, and `SYN_` account identifiers; the input CSVs do **not** contain a demonstration-label column. The generated CSVs and manifest under `outputs/phase1/synthetic_demo/` carry **SYNTHETIC METHODOLOGY DEMONSTRATION — NOT OBSERVED EVERPURE REVENUE** explicitly. Synthetic account IDs never appear in the authoritative account CSV or real-data outputs.
