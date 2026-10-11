# Phase 4 methodology

## Boundary and provenance

The original Case Study 1 asks for an algorithmic routing flow among partner, direct enterprise, and digital workflows using decay risk and ticket velocity. The actual 2,000-row source has no historical revenue series, ticket timestamps, conversion outcomes, fiscal calendar, customer permissions, or validated sales ownership. Phase 4 therefore produces **conditional planning candidates**. It triggers no CRM change, email, partner notification, marketing communication, or customer contact.

The input gate runs the approved source SHA-256 and Phase 2 contract checks through the frozen Phase 3 `validate_phase3_artifacts(..., mode="complete")` function. That gate checks the Phase 3 manifest, current financial assumption register, account schema and grain, nine analytical cells, financial bridges, and an independent account-level financial oracle. A local source join uses `load_phase1_accounts`, which checks source bytes, source columns, one-to-one hierarchy, and ticket sentinel handling. Phase 4 additionally compares all shared Phase 3 quality flags and root IDs. Any contradiction aborts before authoritative output.

The selected economic cell is **base / medium_15pct**, with a 12 continuous-month horizon. The $201,501.66 portfolio analytical expectation and each account's NPV are illustrative net program values, not verified incremental uplift. Historical spend is displayed only as a descriptive source field, never ARR. `1 - expected_reactivation_probability` is an assumption-based 12-month dormancy-persistence proxy. It is not measured revenue decay. Valid ticket count is a snapshot backlog proxy, not velocity. `999` is never treated as 999 genuine tickets or zero tickets.

## Three independent layers

1. Readiness and evidence: source partner Yes/No/Unknown, Green/Yellow/Red/Unknown, valid ticket count/unknown, monthly usage, root relation, source exception flags. `RELATIVELY_COMPLETE`, `MATERIAL_REVIEW`, and `CRITICAL_UNRESOLVED` combine completeness with observed service readiness. The human interpretation of `CRITICAL_UNRESOLVED` is **critical readiness or evidence concern**. Among its 497 accounts, 130 have known partner ownership and a verified critical ticket backlog; that is an observed readiness barrier, not missing evidence.
2. Planning: the versioned rule tree assigns partner, direct, digital, or hold. NPV tertile priority uses fixed thresholds and keeps ties together. Missing health or tickets remain warnings on conditional channel candidates. Unknown partner status is a hold. Red health or five valid open tickets is a service-recovery hold.
3. Authorization: fiscal eligibility, partner authority, sales ownership, consent, and operational approvals are unverified. Every action remains `PLANNING_ONLY`; every execution permission is false.

The enterprise proxy is observed source `monthly_usage_gb_num`, threshold 37,656 GB, the rounded 75th percentile of the provisional cohort. It does not establish actual enterprise classification. No customer discount elasticity is fitted. The 5%, 15%, and 30% Phase 3 offers are hypothetical and distinct from recorded source discounts.

## Hierarchy and confidentiality

Account decisions retain source parent and root IDs. Ownership coordination examines all 2,000 source accounts within each modeled root, including parents and siblings outside the financial cohort. Known Yes/No conflicts, known-plus-Unknown ambiguity, modeled-only conflicts, and mixed modeled channels are separate flags. A modeled account requires root coordination when its root has multiple modeled members or a full-source known Yes/No ownership conflict. Parent and child channel proposals remain intact. Root sums are labeled `ILLUSTRATIVE_SUM_OF_ACCOUNT_MODEL_VALUES`, because separate billable contracts and parent-child independence are unverified. The Phase 3 Monte Carlo assumed conditional independence within root groups.

The source `INACTIVITY_VALUE_GAP_6M` exception contributes to manual-review flags for 984 modeled accounts. The booking-date sequence has artificial-looking structure; these flags request source-data review and do not establish 984 customer service defects. Phase 1 quality definitions remain frozen.

Alternative-scenario priority counts apply the fixed base/15% **dollar cutoffs** to each financial scenario. They measure movement across absolute thresholds, not changes in relative account rank. No within-scenario tertiles are fitted.

Confidential account and root outputs live only under Git-ignored `outputs/phase4/local_only/`. Committable outputs contain broad aggregates, policy and provenance labels. The Phase 5 contract permits only these aggregate files and requires financial and eligibility qualifications. The policy fingerprint is SHA-256 over canonical sorted JSON; it shows exact policy bytes/values, not external authenticity.
