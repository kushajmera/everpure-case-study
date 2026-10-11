# Phase 3 interview defense — financial scenario engine

## Opening answer and boundary

Phase 3 values a hypothetical dormant-account program over 12 continuous months for a provisional 1,144-account cohort. The original assessment brief, externally located and verified on page 2, explicitly asks for a 1,000-run Monte Carlo under varying discount tiers and a three-tier summary. It does not supply the financial inputs or offer percentages. The source has no observed first reactivation, future customer revenue, contribution margin, retention, treatment effect, or untreated counterfactual. Phase 2 supplies **assumed** account hazards, not calibrated propensities. Phase 3 uses those hazards to simulate one first-event time per account and then applies a separately assumed billing and cost policy. The result is `ILLUSTRATIVE_NET_PROGRAM_NPV_NOT_CAUSALLY_ATTRIBUTED`. It is not verified incremental campaign profit.

## A 3–5-minute spoken explanation

“The case source is a single account extract. It has 2,000 unique accounts, but no dated reactivation outcomes or post-event revenue. I first preserve that identification boundary: the 1,144-account financial population is based on reported inactivity of at least two years, and I explicitly retain unresolved fiscal eligibility. Phase 2 created conservative, base and optimistic *assumed* hazards from source-derived customer features. Those are not empirical event rates. I validate the frozen Phase 2 contract, hashes, cohort, and cumulative-probability formula before any financial calculation.

“For each account and replication, I draw one uniform variate and transform it through an exponential first-event hazard. I use 1,000 independent replication vectors. The same vectors are reused across hazard scenarios so differences are paired. A higher assumed hazard moves an account's event earlier for the same draw. I also reuse event times across 5%, 15% and 30% commercial price tiers because I have no evidence that an offer changes customer response. There is one first reactivation per account, and month-3, month-6 and month-12 event indicators all come from that one time.

“I kept the money model separate from historical spend. Each activated account is *assumed* to earn $1,000 gross for every complete service month that fits inside the 12-month horizon. A customer reactivating at month 0.5 first bills at month 2; at month 5.2, first bills at month 7; at month 11.5, has no paid service month before month 12. Commercial discounts reduce revenue, and a 60% contribution margin is applied once. I charge all 1,144 targets $100 outreach at month zero, even when they never return, and $200 activation once at the exact simulated event time. Contribution is collected at billing month-end. A 12% annual effective financial rate discounts those cash flows to the model origin.

“Each of nine hazard-by-offer cells has 1,000 NPVs. I report the mean, median, 5th and 95th conditional outcome percentiles, standard deviation, loss frequency and Monte Carlo standard error. Those describe stochastic first-event variability *conditional on fixed assumptions*. They are not uncertainty bounds on real Everpure profit. As an independent numerical audit, I derive closed-form expected contribution from the probability of being billable at each month and expected discounted activation cost from the exponential event-time density. Every simulated mean is within a predeclared 4.5 standard-error nine-cell diagnostic; the largest observed absolute standardized difference is about 1.885.

“I then use the analytical expectation for one-at-a-time unit-economics sensitivity and break-even thresholds. At base hazards and a 15% offer, expected NPV is about $201,502, while the 1,000-run mean is about $202,912. A lower price discount mechanically raises the result because hazards are held fixed. A separate hypothetical hazard uplift calculates what deeper offers would need to match the 5% case, but there is no observed price elasticity. Finally, I produce a confidential local account-grain table of assumed economic signals and a machine-readable Phase 4 contract. It does not authorize contact or assign routes. Real events, account-period cash flows, margin, retention, treatment/control observations, ownership resolution and fiscal eligibility would be required before presenting a calibrated commercial decision.”

## Worked calculations

### First-event inverse transform

For a hypothetical account with assumed monthly hazard $h=0.012$ and draw $U=0.10$, $T=-\log(0.9)/0.012=8.7800$ months. The account has not reactivated by months 3 or 6, but has by month 12. With the same $U$ and a doubled hazard, $T=4.3900$ months; this is the common-random-number scenario pairing. The draw is synthetic randomness, not a source date.

### Month-by-month account cash flow

Take a hypothetical first event at $T=0.5$, 15% commercial discount, $1,000 gross monthly revenue, 60% margin, $100 outreach and $200 activation. At $t=0$, outreach is $-100$. At $t=0.5$, activation is $-200$. Billing month 1 has zero revenue. Billing months 2 through 12 each have gross revenue $1,000, price deduction $150, discounted revenue $850 and contribution $510, collected at that month-end. There are 11 complete paid periods. If $T=5.2$, billing starts at month 7. If $T=11.5$, the account counts as reactivated but produces no completed paid period by month 12.

### Full discounted NPV and a loss path

With annual effective rate 12%, $DF(t)=1.12^{-t/12}$. For the $T=0.5$ profile above, present-value contribution is $510\sum_{m=2}^{12}DF(m)=\$5,253.47$. Activation PV is $200DF(0.5)=\$199.06$. NPV is **$5,253.47 − $199.06 − $100 = $4,954.41**. For an otherwise identical account with $T=11.5$, no full paid month fits inside the horizon; NPV is **$-100 − $200DF(11.5) = -$279.42**. The model can therefore produce negative paths even with a positive portfolio mean.

### Independent expectation and Monte Carlo example

At hazard $h$, an account qualifies for the full billing period ending month $m$ with probability $P(T\le m-1)=1-e^{-h(m-1)}$. Multiplying that probability by $R(1-d)MDF(m)$ and summing months 1–12 gives expected contribution PV. The month-1 term is zero for continuous positive first-event times. For activation, integrate the cost and discount factor against the first-event density: $C_a\int_0^{12}he^{-ht}e^{-qt}dt=C_a\frac{h}{h+q}(1-e^{-(h+q)12})$, with $q=\log(1+r)/12$. Expected account NPV subtracts outreach; portfolio expectation sums accounts. Independence is unnecessary for this *mean* identity, though the simulated portfolio variance assumes it.

For the actual model's base-hazard / 15% offer, the analytical expected NPV is **$201,501.66**. The 1,000-run mean is **$202,912.47**, a difference of **$1,410.81**. The Monte Carlo standard error is **$1,025.46**, giving $z=1.376$. Finite-run equality is not expected; the discrepancy is within the predeclared 4.5 standard-error nine-cell diagnostic. This comparison checks the implementation under its assumed model. It cannot validate the assumptions.

### Break-even and response example

At base hazards and 5% offer, let $A$ be the sum of expected discounted paid months and $B$ the sum of expected discounted activation indicators. Analytical expected NPV is $R(0.95)(0.60)A-200B-1144(100)$. Setting it to zero and solving for $R$ gives **$364.89 gross per complete paid month**. Solving the same equation for margin gives **21.89%**; the maximum outreach cost is **$311.13 per target**, and maximum activation cost **$2,182.41 per event**. To match the 5% offer's expected NPV, a 15% offer would hypothetically require a **1.132×** hazard multiplier; a 30% offer would require **1.412×**. Those are unobserved treatment-response thresholds, not recommendations.

## Substantive interviewer questions

1. **Why Monte Carlo?** The account event times produce a distribution of cohort outcomes and downside risk. The mean also has a closed form, which independently audits simulation.
2. **What is randomized?** First-event draws only. Hazards, unit economics, discounts, retention and root dependence policy are fixed assumed cases.
3. **Why one event time?** The Phase 2 outputs are cumulative probabilities of *first* reactivation; sampling months independently could make later indicators contradict earlier ones.
4. **Why not add month-3, -6 and -12 expected counts?** They overlap: anyone reactivated by month 3 is already in month 6 and month 12 counts.
5. **What does common randomness buy?** Paired comparisons reduce simulation noise when changing hazard or price while preserving independent replication vectors within each cell.
6. **Why 1,000 replications?** Page 2 of the original assessment explicitly requires a 1,000-run simulation. Each of the nine financial cells receives 1,000 replications. The resulting standard error is reported; more runs reduce numerical noise, not model bias.
7. **Commercial versus financial discount?** The former changes customer price and contribution; the latter changes present value at cash-flow timing.
8. **Why contribution margin?** It converts customer revenue to cash contribution after ongoing service costs assumed to be embedded in the margin.
9. **Why is outreach charged to failures?** Every target incurs the assumed contact cost at month zero, regardless of whether any event occurs.
10. **What does activation cost timing do?** It is paid once at the exact event time through month 12, so late events have a smaller present-value cost and after-horizon events have none.
11. **Why no revenue during the event month?** The declared policy requires a complete service month; the event may occur mid-period and no proration is assumed.
12. **Why can event count exceed billed-account count?** An event between months 11 and 12 has no complete paid period before the horizon.
13. **What does P5–P95 mean?** The 5th and 95th simulated *outcome* percentiles conditional on assumptions, not a confidence interval for true customer economics.
14. **What does Monte Carlo SE mean?** The estimated standard deviation of the sample mean, $s/\sqrt{1000}$, under independent replication vectors.
15. **Why not use historical spend as ARR?** Its accounting period and parent-child consolidation rule are unknown; it cannot be treated as recurring future revenue.
16. **Why is program NPV not incremental uplift?** There is no observed untreated counterfactual, and some assumed reactivation could happen without outreach.
17. **What dominates sensitivity?** Hazard, retention, revenue and margin strongly affect expected value; the one-at-a-time table isolates each assumption.
18. **How is break-even derived?** Solve the closed-form NPV equation for one financial input while holding the others fixed; solve the hypothetical offer response by hazard-multiplier bisection.
19. **How does Phase 4 consume this?** It first calls the reusable `validate_phase3_artifacts(repo_root, mode="handoff")` boundary, then reads the local-only table of assumed probability and analytical economic components plus missingness, quality, cohort and fingerprint flags. Phase 4 must define blocked and review states before routing. A positive assumed NPV is not contact authorization.
20. **What would permit calibration?** Dated at-risk entry and first events, censoring, timestamped pre-event features, account-period revenue and costs, retention, treatment/control data, verified fiscal eligibility and ownership, and a validated accounting convention.
21. **Why not use the source's `discount_tier_pct` as the proposed offers?** That existing account attribute spans 5%–65% and averages 34.9% in the primary cohort. The 5%/15%/30% offers were independently chosen as hypothetical scenarios. The source field supplies no observed response to a newly changed discount, so it cannot identify elasticity.
22. **Why are account NPVs nearly ordered by assumed hazard?** Every account receives the same assumed revenue, margin and costs. Under these baseline values, greater hazard tends to create earlier and more paid periods, while adding some activation cost. Thus most cross-account economic variation is a transformation of Phase 2's assumed hazard. The ranking is not independently validated customer profitability and need not stay monotonic under different costs.
23. **Could parent and child opportunity values overlap?** Yes. Both may represent economic activity that overlaps in reality; the source lacks the contract and billing relationships needed to decide. About 96.8% of base/15% expected NPV lies in root groups with multiple modeled accounts. This flags concentration and possible overlap, not proven double counting.
24. **What does the 60% margin imply about service costs?** The remaining 40% is applied to commercially discounted revenue, so modeled costs within margin fall when the offer discount deepens. If real servicing costs are fixed per account or period, deeper discounts could reduce NPV more severely. The source cannot identify that cost structure.
25. **What do the new artifact checks prove?** Manifest hashes establish consistency of local files and a current financial assumption fingerprint; account reconciliation checks arithmetic; the closed-form oracle independently recomputes economic expectations. Hashes alone do not prove authenticity when someone can replace both a file and its manifest, and none of these checks validates assumed economics against real outcomes.
26. **What happens under several adverse assumptions at once?** A separately labeled hypothetical case uses $750 monthly gross revenue, 45% margin, $150 outreach, $300 activation, a 24% annual financial rate, and a three-paid-month retention cap at base hazards and 15% offer. Its analytical expected NPV is about **−$124,647**. This stresses the assumptions; it is not an estimated downside quantile or an altered primary result.

## Hostile finance and quant questions

1. **“Your revenue is made up. Why should I believe the $201,502?”** The dollar result is a transparent *conditional scenario*, not an estimate from Everpure outcomes. I would use it to identify data requirements and financial thresholds, not to approve spend. The revenue and margin sensitivities quantify fragility.
2. **“The 5% discount wins. Should we eliminate richer offers?”** No. Hazards are held equal by design because the source does not identify offer response. The ranking is mechanical. The hypothetical 1.132× and 1.412× hazard thresholds show what response would be needed; actual price experiments are required.
3. **“Does your 95th percentile imply 90% confidence in real NPV?”** No. It is a P5–P95 range of simulated outcomes conditional on fixed hazards, economics and independence. Parameter, treatment and measurement uncertainty are outside that range.
4. **“You have parent-child accounts. Why independent Bernoulli outcomes?”** Conditional independence is a visible simplifying assumption. Root correlation is unidentified. It does not change the sum of expected marginal NPV if marginal hazards are fixed, but it can widen portfolio dispersion and downside risk. A root-level dependence sensitivity is a useful next extension, not a calibrated fact.
5. **“Is your positive NPV caused by the campaign?”** No. The model charges outreach but has no untreated arm. Causal incremental NPV requires an explicit counterfactual and evidence for treatment effect. Here the exact label is illustrative net program NPV.
6. **“You use a 12% rate on an activation at month 5.2. Is that a monthly 12% discount?”** No. The annual effective rate is converted through $DF(5.2)=1.12^{-5.2/12}$. Month-end contribution uses $DF(m)$.
7. **“The analytical expectation agrees with simulation. Does that prove the business case?”** It checks numerical implementation against the stated event and billing assumptions. Both calculations can agree perfectly while the financial and hazard assumptions are wrong.

## Mathematical glossary and artifact map

| Symbol | Meaning |
|---|---|
| $\lambda_s$ | Assumed scenario baseline hazard per continuous month |
| $\eta_i$ | Phase 2 assumed account log-hazard predictor |
| $h_{is}$ | $\lambda_s e^{\eta_i}$, account/scenario first-event hazard |
| $U_{ik}$ | Shared account/replication uniform draw |
| $T_{isk}$ | Simulated first-reactivation time |
| $R,d,M$ | Assumed monthly gross revenue, commercial price discount, contribution margin |
| $C_o,C_a$ | Outreach per target and activation per event |
| $r,q,DF(t)$ | Annual effective financial rate, $\log(1+r)/12$, and $e^{-qt}$ |
| $NPV$ | Present-value contribution less activation PV and month-zero outreach |

`src/everpure_case/financial_model.py` implements assumptions, event times, pathwise cash flow, closed-form account expectation, and summary statistics. `src/everpure_case/phase3_pipeline.py` validates the frozen inputs, runs the nine-cell simulation, writes sensitivities, thresholds, reconciliation, hash manifest, and the confidential handoff. `outputs/phase3/monte_carlo_run_results.csv` contains 9,000 aggregate run outcomes; `monte_carlo_npv_summary.csv` contains the nine distribution summaries; `monthly_cashflow_summary.csv` contains month-zero through month-12 mean financial bridges; `financial_sensitivity.csv` and `discount_break_even.csv` contain analytical scenarios; `phase4_input_contract.json` defines the local handoff. `notebooks/03_monte_carlo_npv.ipynb` executes six safe aggregate figures. All account identifiers and source-derived economic signals remain in the Git-ignored `outputs/phase3/local_only/` directory.
