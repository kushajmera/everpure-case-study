# Phase 4 decision table and pseudocode

Policy: `docs/PHASE_4_ROUTING_POLICY.json`, version `phase4-routing-policy-v2`. Rules run in listed order. Every modeled row gets exactly one primary rule; warnings accumulate independently. All rows have `execution_authorized=false` and `recommended_action_type=PLANNING_ONLY`.

| Rule | Condition, in order | Required evidence | Disposition | Primary reason |
|---|---|---|---|---|
| R0 | Upstream source, contract, manifest, economic or feature join fails | Phase 1-3 validators | Abort before output | `UPSTREAM_TRUST_FAILURE` |
| R1 | Outside provisional source-reported two-year cohort | Source inactivity status | Full-cohort `HOLD_REVIEW`, no score | `SOURCE_INACTIVITY_CONFLICT` or `SOURCE_INACTIVITY_UNKNOWN` |
| R2 | Invalid identity or root relation | Account and hierarchy | `HOLD_REVIEW` | `IDENTITY_OR_HIERARCHY_CONFLICT` |
| R3 | Partner ownership unknown | Source partner field | `HOLD_REVIEW` | `PARTNER_OWNERSHIP_UNRESOLVED` |
| R4 | Red health or valid open tickets >=5 | Source health, valid ticket snapshot | `HOLD_REVIEW` | `SERVICE_RECOVERY_REQUIRED` |
| R5 | Known partner Yes | Source partner field | `PARTNER_LED_CANDIDATE` | `SOURCE_PARTNER_MANAGED` |
| R6 | Known partner No, valid usage >=37,656 GB | Source partner and monthly usage | `DIRECT_ENTERPRISE_CANDIDATE` | `USAGE_SCALE_PROXY` |
| R7 | Known partner No, valid usage below 37,656 GB | Source partner and monthly usage | `DIGITAL_NURTURE_CANDIDATE` | `KNOWN_NONPARTNER_LOWER_SCALE` |
| R8 | Remaining case, including missing scale | Source partner and usage | `HOLD_REVIEW` | `SCALE_EVIDENCE_UNRESOLVED` |

The 37,656 GB scale cut is the rounded observed 75th percentile of this provisional cohort. It is an analyst-selected scale heuristic, not observed enterprise classification. Valid tickets 3-4 mean elevated backlog; 5 or more means critical. Red health alone prompts service recovery. Missing health or tickets carry review flags without automatically erasing an otherwise interpretable channel. Unknown ownership does block planning channel assignment. A positive illustrative NPV never overrides those rules.

```text
validate committed Phase 1-3 inputs and independent financial oracle; abort on failure
reconcile source accounts: 1,144 modeled; 562 conflicts; 294 unknown
for each modeled account, join its one source feature record by account_id:
    compare root and all shared missingness/quality flags; abort on contradiction
    select only base / medium_15pct Phase 3 account economics
    apply R2, R3, R4, R5, R6, R7, R8 in that order
    priority = LOW if NPV <= 161.51698172008832
               else MEDIUM if NPV <= 200.26496145151106 else HIGH
    label dormancy proxy = 1 - selected expected_reactivation_probability
    classify source evidence, service backlog, and all review flags independently
    set fiscal eligibility and execution authorization false
group by root using all 2,000 source records for ownership evidence;
    preserve modeled child channels, flag known conflicts and unknown ambiguity
emit local confidential decisions; emit safe aggregate counts and Phase 5 contract
```

Ties at the two NPV cutpoints stay in the lower tier. The Phase 3 CSV is parsed with `float_precision="round_trip"`: 82 accounts equal the lower cutpoint and 147 equal the upper cutpoint. These are frozen base/15% tertile cutpoints; NPV and assumed hazard are dependent model outputs and receive no double weighting.

| Synthetic evidence | Result | Additional qualification |
|---|---|---|
| Partner Yes, Green, zero valid tickets | R5 partner candidate | Partner authority and contact permissions unverified |
| Partner No, Green, 40,000 GB, zero tickets | R6 direct candidate | Usage is only a scale proxy |
| Partner No, Yellow, 1,000 GB, one ticket | R7 digital candidate | Marketing consent unverified |
| Partner unknown, highest modeled NPV | R3 hold | Opportunity remains visible |
| Partner No, Red, 5 valid tickets | R4 hold | Service recovery required |
| Partner No, unknown health, 40,000 GB | R6 direct candidate | Health review flag; no Green claim |
| Partner No, sentinel 999, 40,000 GB | R6 direct candidate | Backlog unknown, ticket review flag |
| Partner No, missing usage | R8 hold | No enterprise status inferred |
| Parent partner Yes, child partner No | Individual routes preserved | Root ownership coordination required |

Reason codes are stable uppercase identifiers from the rule table and `gtm_routing.py`. Further warnings are `HEALTH_UNKNOWN`, `TICKET_BACKLOG_UNKNOWN`, `TICKET_SENTINEL_999`, `SOURCE_MANUAL_REVIEW`, `SCALE_UNKNOWN`, `FISCAL_ELIGIBILITY_UNCONFIRMED`, `ACCOUNT_HEALTH_REVIEW_REQUIRED`, `ELEVATED_TICKET_BACKLOG`, and `ROOT_COORDINATION_REQUIRED`. The local root table distinguishes `MODELED_PARTNER_OWNERSHIP_CONFLICT`, `FULL_SOURCE_KNOWN_OWNERSHIP_CONFLICT`, `OUT_OF_COHORT_OWNERSHIP_CONFLICT`, `FULL_SOURCE_UNKNOWN_OWNERSHIP_AMBIGUITY`, `MIXED_PLANNING_CHANNELS`, and `MULTI_ACCOUNT_ROOT_COORDINATION`. R1 is applied by cohort disposition logic after source segmentation, before account-level R2–R8 routing.
