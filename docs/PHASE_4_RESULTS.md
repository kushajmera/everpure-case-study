# Phase 4 results: conditional GTM planning

The engine passed the frozen Phase 1 source gate, Phase 2 assumption contract, and Phase 3 complete artifact and independent financial oracle. Input: 10,296 Phase 3 account-scenario-offer records with the contract's 29 fields. Reference: base reactivation scenario, hypothetical 15% commercial price discount, 12 continuous months. All values below are planning outputs.

| Population | Accounts |
|---|---:|
| Source | 2,000 |
| Provisional source-reported two-year modeled | 1,144 |
| Source/calendar inactivity conflicts, excluded from financial model | 562 |
| Inactivity unknown, excluded from financial model | 294 |

Fiscal-year eligibility remains unconfirmed for every modeled account.

| Planning disposition | Accounts | Modeled cohort % |
|---|---:|---:|
| Partner-led candidate | 247 | 21.6 |
| Direct-enterprise candidate | 66 | 5.8 |
| Digital-nurture candidate | 205 | 17.9 |
| Hold/review | 626 | 54.7 |

The holds comprise 367 unknown partner ownership records and 259 known ownership records requiring service recovery under the policy. High, medium, and low illustrative NPV priority counts are 288, 418, and 438. Fixed cutpoints are $161.51698172008832 and **$200.26496145151106**, with equality in the lower tier. Round-trip parsing preserves 82 accounts tied at the lower cutoff and 147 tied at the upper cutoff. This is an ordering convention; it is not a calibrated account outcome forecast.

Source evidence requires partner review for 367 accounts, health review for 703, ticket review for 591, and root coordination for **1,131**. Evidence is relatively complete for 46, needs material review for 601, and has a critical readiness or evidence concern for 497. Among the last group, 130 have known partner ownership and a verified critical ticket backlog; the category is not exclusively about missing evidence. Service snapshot states: 189 critical backlog, 211 elevated backlog, 372 low backlog, 181 observed zero open tickets, and 191 unknown. Neither the zero count nor any other snapshot yields ticket velocity. The artificial-looking source booking-date sequence contributes `INACTIVITY_VALUE_GAP_6M` manual-review flags for 984 modeled accounts; these are not verified service defects.

The high illustrative priority tier contains **187 unknown-health accounts out of 288**, showing why financial order and evidence readiness must be read separately. The safe priority-by-evidence summary and high-priority missingness counts in `data_readiness_summary.csv` expose this sensitivity without changing frozen Phase 3 scores.

All 295 modeled roots reconcile to 1,144 account records. Among modeled members only, 257 roots have multiple modeled accounts, 145 have known Yes/No ownership conflict, and 215 have mixed proposed channels. Across **full source membership**, 235 modeled roots have known Yes/No ownership conflict. The union of modeled multi-account roots and full-source known conflicts requires coordination for 282 roots and 1,131 modeled accounts. Out-of-cohort members inform ownership coordination but receive no modeled NPV or route. Root-level NPV sums are illustrative sums of separate account model values; billable independence is unverified.

The base/15% analytical expected program NPV is **$201,501.66**, summing the selected 1,144 account values once. The nine scenario cells are alternatives and must not be added together. Alternative-scenario priority counts apply the fixed base/15% dollar cutoffs; this is an **absolute-threshold sensitivity**, not a relative re-ranking. Assumed hazard and NPV share the same model inputs, so Phase 4 does not double count them. Unknown health and sentinel tickets use reference-level Phase 2 scoring conventions and can bias high-priority rankings. The illustrative financial result is neither verified profit nor causal incremental uplift. Deeper discounts are mechanically less favorable in the fixed-response primary model.

Two separately specified adverse stresses produce distinct results:

| Stress vector | Hazard multiplier | Monthly gross | Margin | Outreach | Activation | Annual financial discount | Max paid months | Commercial discount | Analytical expected NPV |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Committed Phase 3 combined adverse | 1.0 | $750 | 45% | $150 | $300 | 24% | 3 | 15% | **−$124,647.432973** |
| Separate alternative compounded | 0.5 | $750 | 60% | $150 | $200 | 12% | 3 | 15% | **−$124,704.050145** |

These values refer to different assumption vectors. The committed Phase 3 financial engine and its stress output remain unchanged.

**Authorized customer-contact actions: zero.** No campaign, partner notification, or CRM update occurred. Any operational rollout needs confirmed fiscal eligibility, current service and ownership data, customer permissions, partner authority, sales owner approval, and human review of mixed roots.
