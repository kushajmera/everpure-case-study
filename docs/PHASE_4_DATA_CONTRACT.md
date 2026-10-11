# Phase 4 data contract

Input contract: `outputs/phase3/phase4_input_contract.json`, version `phase3-to-phase4-v1`; source SHA `6863ea0014f050355bf9e0c5166e2284edfe8521ea3d87a2a2fa168177a229bc`. Frozen Phase 3 financial fingerprint: `b953c02d3fdcfacc62d9e6755889040e9f8bd12db7c830a88c79f5c991267e70`. Phase 2 fingerprint: `6195ba2e90c95976ed91b7bdd42509341fd22e71e6b2bb5aed2e5d2a6d346ee7`.

The local economic input has the exact 29 columns specified in the input contract, 10,296 rows, 1,144 unique account IDs and grain `(account_id, reactivation_scenario, commercial_discount_tier)`. Phase 3's validator checks all nine financial cells and independent analytical economics. Phase 4 selects the base/15% row once per account and joins source partner, health, ticket, region, usage, parent, and root by validated `account_id`.

Confidential local outputs:

| File | Grain | Rows |
|---|---:|---:|
| `local_only/account_routing_decisions.csv` | modeled account | 1,144 |
| `local_only/cohort_dispositions.csv` | source account | 2,000 |
| `local_only/root_coordination.csv` | modeled root | 295 |

Safe aggregate outputs are `routing_channel_summary.csv`, `commercial_priority_summary.csv`, `priority_evidence_summary.csv`, `data_readiness_summary.csv`, `service_barrier_summary.csv`, `root_coordination_summary.csv`, `cohort_reconciliation_summary.csv`, `scenario_priority_sensitivity.csv`, `routing_rule_counts.csv`, and `metrics.json`. The `phase4-to-phase5-v2` contract records their hashes, schemas, grains, denominators, fingerprints, financial semantics, and versioned required disclosures. The `phase4-artifact-manifest-v2` manifest hashes all safe and local artifacts. `validate_phase4_artifacts` revalidates frozen upstream files, independently rebuilds all decisions and summaries in memory, then compares them by unique keys; hashes alone are insufficient. The sensitivity CSV applies fixed base/15% dollar cutoffs, not within-scenario ranks. Never present local IDs or root mappings.

The 562 conflict and 294 unknown records have `financial_score_available=false`; no probability or NPV is inferred for them. Every modeled fiscal eligibility and operational contact permission is false. Source categories remain tri-state, and sentinel tickets remain unknown.
