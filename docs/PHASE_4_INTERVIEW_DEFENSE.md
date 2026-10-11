# Phase 4 interview defense

## Spoken explanation (3–5 minutes)

“The Everpure brief asks for an algorithmic GTM router across partner, direct enterprise, and digital workflows using decay risk and ticket velocity. I built an executable deterministic policy with those three candidate channels plus a hold state. The supplied source is a 2,000-account snapshot, so it cannot measure historical revenue decay or ticket velocity. I use a clearly labeled 12-month assumed dormancy-persistence proxy from Phase 3 and valid open tickets as a backlog snapshot. I never describe either as an observed time-series trend.

First I validate the source hash and frozen Phase 2 and 3 contracts. The Phase 3 validator independently recomputes all nine analytical account and portfolio financial cells. Then I select one reference cell, base with a hypothetical 15% discount, and join the 1,144 provisional two-year accounts to the verified Phase 1 source features by account ID. I compare root mapping and every shared missingness or quality flag. Contradictions abort the run.

The rule order holds unknown partner ownership, Red health, or at least five valid open tickets for review. Known partner accounts become partner-led candidates. Known non-partner accounts with at least 37,656 GB in the source monthly-usage field become direct-enterprise candidates; lower valid usage becomes digital nurturing. The usage threshold is the provisional cohort's rounded upper quartile, only a scale heuristic. Missing health and ticket counts retain review flags without automatically erasing an otherwise useful conditional recommendation.

Commercial priority is separate. I use the selected Phase 3 account NPV and fixed tertile cutpoints, keeping ties together. I do not combine NPV and assumed hazard as independent predictors. I also keep an evidence-quality tier and authorization field separate, so a high-value account can be unresolved and unauthorized. Every account remains planning only because fiscal eligibility, contact permissions, partner authority, and operational approvals are unverified.

The result is 247 partner, 66 direct, 205 digital, and 626 hold/review, summing to 1,144. The other 856 source accounts appear in a full 2,000-account reconciliation without invented economics. All 295 modeled roots reconcile, and mixed ownership or channels are flagged without forcing children to inherit a parent route. Zero customer-contact actions were authorized or executed. The safe aggregate outputs and contract support a qualified executive presentation, while real account decisions remain local and Git-ignored.”

## Questions and defensible answers

1. **What was the mandate?** A flowchart or pseudocode routing dormant accounts among partner, direct, and digital workflows based on decay risk and ticket velocity. The original brief also asks for a five-slide executive deck, reserved for Phase 5.
2. **Why deterministic rules?** There are no observed contact outcomes or treatment labels to train or validate a new predictor; explicit rules expose thresholds and precedence.
3. **Why no new ML fit?** A fitted customer conversion model would manufacture certainty from a snapshot. The Phase 2 Cox fit is isolated synthetic methodology, not Everpure outcome evidence.
4. **How is 2,000 reduced to 1,144?** Source-reported inactivity >=2 years gives the provisional modeled cohort; 562 source/calendar conflicts and 294 unknowns remain in review.
5. **Are these fiscal-year eligible?** No. No fiscal calendar or verified eligibility determination is supplied.
6. **How is the handoff trusted?** Source SHA, Phase 2 contract and fingerprint, Phase 3 manifest and assumption freshness, exact 29-field schema, 10,296 row grain, nine-cell bridges, and independent economic oracle.
7. **Why join Phase 1?** The financial export has only missingness flags; it does not contain actual partner Yes/No, health category, valid ticket count, usage, or region.
8. **How is the join safe?** It validates unique IDs and one-to-one source match, rejects missing rows and root mismatches, and compares all shared Phase 3 flags with source-derived values.
9. **Why hold unknown ownership?** A blank partner field cannot safely imply either direct sales or partner management.
10. **What qualifies for partner-led?** Observed source partner Yes, absent higher-priority hold. Partner authority remains unverified.
11. **What qualifies for direct?** Source partner No and valid monthly usage at least 37,656 GB, absent a higher hold. This is a scale proxy, not verified enterprise status.
12. **What qualifies for digital?** Source partner No and valid usage below the scale cut, absent a higher hold. Marketing consent is still unknown.
13. **Why hold/review?** It preserves unknown ownership, source conflicts, serious service barriers, and missing scale evidence rather than silently inventing a route.
14. **Is dormancy persistence observed decay?** No. `1 - assumed 12-month reactivation probability` is a model proxy; historical account revenue decay cannot be reconstructed.
15. **Is ticket velocity measured?** No. Valid open tickets are a count snapshot without creation or resolution timestamps.
16. **How is sentinel 999 handled?** It is unknown backlog and a review flag, never 999 valid tickets or zero.
17. **What happens with unknown health?** It stays unknown, with a health review warning. Phase 2 used a Green-reference scoring contribution, which can overstate rank confidence.
18. **How is NPV used?** As one illustrative commercial-ordering signal from the frozen base/15% account row, separate from routing evidence and contact authorization.
19. **Why are base account NPVs all positive?** The analyst-selected Phase 3 unit economics and assumed hazards imply it; positivity is not observed profitability or permission to contact.
20. **Why not score NPV and hazard together?** The NPV already depends on the assumed hazard. Combining both as independent evidence double counts the same model signal.
21. **How does service affect routing?** Red health or at least five valid open tickets produces a service-recovery hold. Three or four tickets are elevated warnings.
22. **What happens with mixed roots?** Account routes remain intact. Ownership evidence uses all source members of each modeled root, even an out-of-cohort parent. Known conflicts and unknown ambiguity are separate flags; 235 roots have full-source known conflicts, and 282 require coordination.
23. **Can parent and child NPVs be added as revenue?** The arithmetic sum is illustrative only. Separate billable opportunities and within-root independence are unverified.
24. **Do discounts reflect observed response?** No. The 5/15/30% offers are hypothetical and differ from source recorded discounts. No elasticity is estimated.
25. **Why is positive NPV not enough to contact?** Fiscal eligibility, contact rights, partner authority, and approvals are missing. Planning and authorization are different fields.
26. **How do route counts reconcile?** 247+66+205+626=1,144; 1,144+562+294=2,000; root modeled account counts sum to 1,144.
27. **How is the policy reproduced?** The JSON policy fixes thresholds and version; the code records rule and reason codes; the manifest hashes outputs and the policy fingerprint.
28. **What would operationalization need?** Verified fiscal calendar, current health and tickets with timestamps, approved owners, partner contracts, contact rights/consent, billing independence, human root review, and outcome monitoring.
29. **What can Phase 5 claim?** Conditional candidate counts and qualified illustrative financial results; zero authorized outreach. It cannot claim measured causal uplift, ticket velocity, or verified consolidated revenue.
30. **How does the diagram match code?** Flow nodes R0–R8 mirror upstream validation, cohort exclusion, `route_account` precedence, root coordination, and authorization false.

## Hostile checks

1. **“Your top NPV account has no partner value. Why route direct?”** I do not. R3 holds it while keeping its financial priority visible.
2. **“Phase 2 treated missing health as Green, so can you call it healthy?”** No. Source health remains `UNKNOWN`, and the score convention is a sensitivity caveat.
3. **“A row has 999 tickets. Is that a severe backlog?”** It is a sentinel and becomes unknown; severity cannot be inferred from it.
4. **“Can a partner Yes row automatically notify the partner?”** No. It is a conditional planning candidate with authorization false.
5. **“Could a changed financial CSV pass if its hash is refreshed?”** A hash alone could. The frozen Phase 3 validator also recomputes an independent account and portfolio economic oracle from validated Phase 2 assumptions.
6. **“Why does a child disagree with its parent?”** Source attributes are preserved per account. A root coordination flag signals human ownership review; no duplicate executable actions are issued.
7. **“Does 181 zero-ticket accounts prove no ticket velocity?”** No. Zero open tickets is a point-in-time backlog only.
8. **“Is your $201,501.66 recoverable revenue?”** No. It is an illustrative net program analytical NPV under selected assumptions, without a measured untreated counterfactual.

## Worked hypothetical cases

| Case | Source evidence | Rule and result | What remains open |
|---|---|---|---|
| Partner | Partner Yes, Green, zero valid tickets | R5 partner candidate | Partner authority, fiscal eligibility, contact rights |
| Direct | Partner No, Yellow, 40,000 GB, one valid ticket | R6 direct candidate | Sales ownership and consent |
| Digital | Partner No, Green, 1,000 GB, zero tickets | R7 digital candidate | Marketing consent |
| Hold | Partner unknown, high illustrative NPV | R3 hold | Ownership, despite financial priority |
| Root collision | Parent partner Yes, child partner No | Separate R5/R6 or R7; root flag | Human commercial ownership coordination |
| High NPV, unknown health | Partner No, 40,000 GB | R6 candidate with `HEALTH_UNKNOWN` | Service assessment |
| Sentinel | Partner No, 40,000 GB, ticket 999 | R6 candidate, unknown backlog | Valid ticket count |

Every worked candidate still has `execution_authorized=false`.

## Rule-to-code and field glossary

R0 is `phase4_pipeline._compute_expected` calling `phase3_pipeline.validate_phase3_artifacts` and `enrich`; R1 is `_cohort`; R2–R8 are `gtm_routing.route_account`; full-source root coordination is `_roots`; the safe Phase 5 interface is `_safe` and the independently recomputing `validate_phase4_artifacts`.

| Field or measure | Provenance |
|---|---|
| `partner_managed_clean`, `health_clean`, `tickets_clean`, `ticket_sentinel`, `monthly_usage_gb_num`, region, parent | Phase 1 normalized source fields |
| Root ID, source inactivity cohort, quality flags | Phase 1 source-derived |
| Reactivation probability, hazard | Phase 2 assumption-based scenario |
| Account NPV and financial components | Phase 3 illustrative analytical model |
| Dormancy persistence | Phase 4 complement of assumed 12-month probability |
| Open backlog status | Phase 4 classification of valid source ticket snapshot |
| Ticket velocity, historical revenue decay, customer permission | Unobserved |
