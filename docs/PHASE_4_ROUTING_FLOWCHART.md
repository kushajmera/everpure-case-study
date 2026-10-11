# Phase 4 GTM decision flow

This is the rule order in `gtm_routing.route_account`. It creates planning candidates, never contact instructions. All modeled fiscal eligibility is unconfirmed.

```mermaid
flowchart TD
    A[Validate source SHA, Phase 2 contract, Phase 3 manifest, assumptions, 29 fields, 9 financial cells] -->|failure R0| X[Abort; emit no authoritative routes]
    A -->|pass| B{Source-reported two-year provisional cohort?}
    B -->|no R1| C[Full-cohort HOLD_REVIEW; no financial score]
    B -->|yes| D[One-to-one source enrichment and flag checks]
    D --> E{Identity or hierarchy conflict?}
    E -->|yes R2| H[HOLD_REVIEW]
    E -->|no| F{Partner status unknown?}
    F -->|yes R3| H
    F -->|no| G{Red health or valid tickets at least 5?}
    G -->|yes R4| H
    G -->|no| I{Partner managed Yes?}
    I -->|yes R5| P[PARTNER_LED_CANDIDATE]
    I -->|no| J{Valid monthly usage at least 37,656 GB?}
    J -->|yes R6| Q[DIRECT_ENTERPRISE_CANDIDATE]
    J -->|no, valid lower usage R7| R[DIGITAL_NURTURE_CANDIDATE]
    J -->|usage unknown R8| H
    H --> S[Keep base/15 percent illustrative NPV priority and evidence flags separate]
    P --> S
    Q --> S
    R --> S
    S --> T[Inspect full-source root ownership and modeled channels; flag coordination]
    T --> U[execution_authorized=false; PLANNING_ONLY]
    U --> V[Reconcile 1,144 modeled, 2,000 source, 295 roots; safe aggregates]
    C --> V
```

The financial score is a frozen Phase 3 assumption, not an observed propensity or causal uplift. `1 - expected_reactivation_probability` is an **assumed dormancy-persistence proxy** over 12 abstract continuous months. Valid open tickets form a **snapshot backlog proxy**; ticket velocity and historical revenue decay are unobserved. Sentinel 999 and missing tickets remain unknown.
