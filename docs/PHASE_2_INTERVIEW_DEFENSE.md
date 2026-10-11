# Phase 2 interview defense

## Thirty core questions and answers

1. **What is survival analysis?** It models the time until a defined event, while allowing some subjects to leave observation before the event is seen. Here the event would be account reactivation.
2. **Why is reactivation a time-to-event question?** A 3-month and a 12-month reactivation probability differ even for the same account. A single yes/no label would discard timing and censoring.
3. **Why define an origin?** Duration has no meaning without a start. Synthetic subjects enter at invented enrollment t=0; the account scenario uses 2026-10-09 by convention.
4. **What is right censoring?** We know the event was not observed up to a follow-up endpoint, but not what happens afterward. In the simulation the endpoint is an independent random loss time capped at 36 months.
5. **Hazard versus probability?** Hazard is an instantaneous event rate conditional on still being at risk. Cumulative probability integrates that rate over a duration. A hazard ratio of 1.5 is not a 50% event probability.
6. **What is Cox proportional hazards?** It describes `h(t|x)=h0(t)exp(beta'x)` for an unspecified baseline hazard and covariate-dependent relative hazard.
7. **Why semiparametric?** Coefficients have a finite-dimensional parametric form; the baseline hazard's time shape is left unspecified.
8. **What does partial likelihood estimate?** It compares the covariates of each observed event subject with the risk set at that event time to estimate relative effects, without first specifying `h0(t)`.
9. **Why estimate baseline survival later?** A relative hazard tells us how two profiles compare. Absolute `S(t|x)` needs cumulative baseline hazard or baseline survival. Lifelines' reported baseline curve uses its mean covariate profile; predict the all-zero profile separately.
10. **How were synthetic event times generated?** For 1,600 subjects with seed 20261009, draw binary/normal covariates; use hazard `0.035 exp(0.45 health - 0.35 engagement + 0.25 partner)` per continuous month; sample an exponential event time.
11. **How was censoring simulated?** Draw an independent Uniform(8,48) month endpoint, cap it at 36, record the smaller of event and censor time, and mark an event only if event time is at or before censoring.
12. **What actually entered Cox fitting?** `duration_months`, `event_observed`, and the three pre-event synthetic covariates. Synthetic truth fields and all Everpure account fields are excluded.
13. **How do you interpret fitted hazard ratios?** `exp(fitted coefficient)`. The synthetic health proxy estimate is 0.505, so its fitted hazard ratio is 1.658, holding the other proxies fixed.
14. **What does proportional hazards assume?** A covariate's hazard ratio is constant over follow-up. It does not require a constant baseline hazard.
15. **How did you check proportional hazards?** Lifelines' rank-transformed Schoenfeld residual test reports p-values of 0.283, 0.252, and 0.939 for this seeded run. None rejects at 0.05; a rejection would be reported, not erased by changing the seed.
16. **What is concordance?** It measures how often higher predicted risk orders comparable event times correctly. The synthetic fit has 0.624 in-sample and 0.595 on an independent synthetic holdout.
17. **Does that accuracy validate Everpure?** No. Both populations and outcomes are invented. The result proves executable methodology only.
18. **Why not use last booking dates as events?** There is one date per account, no repeated reactivation history, and every booking date equals 2019-01-01 plus an account-ID offset. Contract dates are likewise deterministic.
19. **How were 1,144 accounts selected?** Phase 1's source-reported `years_inactive >= 2` flag. It is an explicit scenario-population policy.
20. **Why is that not confirmed fiscal eligibility?** The brief says two fiscal years, but the fiscal boundary, rule interpretation, and source inactivity measurement date are unknown. Phase 1 found 562 conflicts with a calendar proxy and 294 unknowns.
21. **What is the account scenario model?** A constant, explicitly assumed monthly hazard `lambda_s exp(eta_i)` for each scenario `s`, with the same assumed feature effects across scenarios.
22. **How is an account probability computed?** At horizon `t`, calculate cumulative hazard `lambda_s*t*exp(eta_i)` and then `1-exp(-cumulative hazard)`. The code uses `expm1` for numerical stability.
23. **How are expected counts computed?** Sum account probabilities within scenario and horizon. For example, the base 12-month sum over 1,144 accounts is 128.724.
24. **Why aren't scenario effects learned coefficients?** The source supplies no reactivation events or censoring records. The values live in a versioned assumption register and are not copied from the synthetic Cox fit.
25. **How are missing fields handled?** The scoring rule gives unknown health the Green-reference contribution, unknown partner the direct-reference contribution, and missing tickets the zero-ticket-reference contribution, each with an explicit missingness flag. This is a reference-level assumed contribution with explicit missingness flags, not a source-data correction or evidence of an observed business effect.
26. **How does hierarchy matter?** Phase 1 provides one-to-one account-to-root joins. Root membership may correlate outcomes, so expected totals still sum, but total-count variance cannot be inferred by assuming independent accounts.
27. **What does sensitivity establish?** It shows how selected hazard, effect, missing-health, horizon, and hypothetical cohort policies change assumed outputs. It does not calibrate true conversion behavior or supply confidence intervals. Missingness can also change account ranking even when aggregate totals stay within a scenario band.
28. **Why isn't probability incremental revenue?** Reactivation could yield different or no incremental cash flow. Spend period, consolidation, margin, campaign cost, discount policy, and retention are missing.
29. **What would permit production calibration?** Timestamped dormant-cohort origin, reactivation date, censor date, pre-origin covariates, complete follow-up rules, enough events, and independent held-out real validation.
30. **What would invalidate this methodology?** A fit that ingests true times after censoring, real IDs in the synthetic cohort, synthetic coefficients in account scoring, account-ID-derived dates as outcomes, multiplied hierarchy rows, unflagged missing values, reversed scenario ordering, or failed reconciliation.

## Worked calculations

**Cox hazard ratio.** Suppose a fitted log coefficient is 0.4055. Step 1: exponentiate, `exp(0.4055)≈1.500`. Step 2: compare two otherwise equal profiles differing by one unit: the first has 1.5 times the other's *instantaneous* hazard. Step 3: do not infer their 12-month cumulative probabilities without baseline survival. In the actual synthetic run the health proxy coefficient is 0.5053, giving `exp(0.5053)=1.6575` and a 95% HR interval 1.4697–1.8694.

**Cumulative survival.** With a constant assumed hazard 0.012/month, no feature adjustment, and 12 months: cumulative hazard is `0.012×12=0.144`; survival is `exp(-0.144)=0.86589`; cumulative event probability is `1-0.86589=0.13411`. This arithmetic is a scenario assumption, not an observed Everpure rate.

**Censoring.** An invented subject's true event is at month 14 and independent censoring is at month 10. The observable duration is `min(14,10)=10` months and event flag is 0. We know only that no event was observed through month 10. If a second subject's event is at month 7 and censoring at month 10, observable duration is 7 and event flag is 1. The true month-14 time is never fed to Cox as an observed event.

**Complete hypothetical scenario calculation.** Consider an invented child profile with Red health, partner-managed ownership, and one valid ticket. No booking or contract date enters scoring. Under `phase2-assumptions-v1`, Red contributes -0.35, partner management +0.15, child position -0.10, and tickets `-0.08×ln(1+1)=-0.05545177`. Thus `eta=-0.35545177` and `exp(eta)=0.70085674`. The base monthly hazard is `0.012×0.70085674=0.00841028`. At 12 months cumulative hazard is `0.10092337`; survival is `exp(-0.10092337)=0.90400230`; assumed first-reactivation probability is `0.09599770`. This is a demonstration profile, not a source account or a measured response probability.

**Baseline profile distinction.** At 36 synthetic months, the fitted lifelines baseline survival is approximately 0.1798 at the model's mean covariate profile. The fitted all-zero profile has survival approximately 0.2846. Under the true generating exponential process, all-zero survival is `exp(-0.035×36)≈0.2837`. The three quantities answer different questions; the first is not the all-zero curve.

## Cox versus account scenario model

| Question | Synthetic Cox lane | Everpure account scenario lane |
|---|---|---|
| Outcome data | Generated event/censor histories | No observed outcome; Phase 1 account features only |
| Baseline hazard | Left unspecified for relative fit, then estimated for absolute survival | Constant monthly value chosen in register |
| Covariate effects | Estimated by partial likelihood on synthetic histories | Chosen in register; never fitted |
| Validation | Synthetic diagnostics and independent synthetic holdout | Arithmetic, integrity, and sensitivity checks; no empirical calibration |
| Interpretation | Methodological proof | Conditional illustrative business inputs |

## Hostile technical questions

1. **“You ran Cox, so where is the Everpure propensity model?”** There is none. The Cox fit is exclusively on invented `SYN_` subjects. The real account probabilities use a different module and manually registered hazards/effects. A boundary test runs that account lane with synthetic fitting disabled.
2. **“Your Schoenfeld p-values exceed 0.05, so you proved proportional hazards.”** No. Failure to reject is not proof, and the diagnostic has finite power. This run happens to use data generated under a PH process; we publish p-values and warnings without seed shopping.
3. **“You used 1,144 eligible customers. Isn't that false?”** The output calls them a **provisional scenario cohort** based on source-reported inactivity. Fiscal eligibility is unconfirmed, and the full 2,000 rows reconcile into 1,144 primary, 562 conflict, and 294 unknown.
4. **“Why did the expanded cohort produce more events? Does it have higher propensity?”** At 12 months, adding all disputed and unknown accounts increases the denominator to 2,000 and expected count to 225.180; mean probability changes only from 0.11252 to 0.11259. Most of the increase is population size, not better per-account propensity.
5. **“Can I multiply the 128.724 expected reactivations by average historical spend for NPV?”** No. Historical spend lacks a period and parent-child consolidation rule, and reactivation is not necessarily incremental revenue. Phase 3 needs margin, incremental cash-flow definition, costs, discount policy, retention, and a financial discount rate.
6. **“Is assigning zero effect to missing tickets data fabrication?”** Source ticket 999 remains missing, with its sentinel and missingness flags. The scoring step nevertheless assigns it the zero-ticket-reference contribution. That is a disclosed assumption, not a claim that the source observed zero tickets or that the true effect is zero. The same reference-level convention applies to unknown health and partner ownership.
7. **“Does the 12-month count prove missingness is harmless?”** No. Scoring unknown health as Yellow or Red changes the 12-month base expected count from 128.724 to about 121.091 or 112.374. A frequency-weighted effect based on known-health accounts gives about 120.269. Account rankings can shift more than the aggregate total suggests.

## Notation glossary

`T`: time from defined origin to reactivation; `t`: forecast horizon in continuous months; `h(t|x)`: instantaneous event hazard conditional on covariates; `h0(t)`: Cox baseline hazard; `lambda_s`: chosen baseline monthly hazard for scenario `s`; `beta`: synthetic Cox fitted log-hazard coefficients; `gamma`: chosen Everpure scenario effects; `eta=gamma'x`: assumed log-hazard predictor; `S(t|x)`: survival probability through `t`; `1-S(t|x)`: cumulative event probability; `delta`: observed event indicator; `C`: censoring endpoint; `HR=exp(beta_j)`: conditional instantaneous hazard ratio.

## Code-to-output map

| Function | Output |
|---|---|
| `verify_authoritative_source` | Source SHA/row/spend gate before Phase 2 |
| `generate_synthetic_cohort` | `synthetic_survival_cohort.csv`, generation manifest |
| `fit_synthetic_cox` | Coefficients, diagnostics, baseline survival, synthetic predictions |
| `kaplan_meier` | `synthetic_kaplan_meier.csv` |
| `load_phase1_accounts` / `reconcile_cohort` | `cohort_reconciliation.csv` |
| `engineer_features` / `project_accounts` | Account probabilities and scenario summary |
| `scenario_sensitivity` | `scenario_sensitivity.csv` |
| `phase2_pipeline.run_pipeline` | Full outputs, metrics, manifest, Phase 3 JSON contract |

## Four-minute spoken defense

> Phase 2 asks a time-to-event question: how likely is a currently dormant account to reactivate over the next 3, 6, or 12 months? I first checked whether the supplied Everpure file could support that estimate. It cannot. We have 2,000 account snapshots, no observed reactivation events, no event timestamps, and no observation or censoring endpoints. Phase 1 also showed that every booking date is determined by the numeric account ID. Treating those dates as event histories would create false evidence.
>
> I therefore built two separate analytical lanes. The first demonstrates genuine Cox modeling on 1,600 independently generated synthetic subjects. Each enters at synthetic month zero. I generated an event time using an exponential proportional-hazards process and an independent censoring time, then fit lifelines Cox to the observed minimum duration and event indicator. The model never sees a subject's true event time after censoring. We export the generating coefficients separately from the fitted ones, along with hazard ratios, confidence intervals, baseline survival, survival curves, Kaplan–Meier, Schoenfeld diagnostics, and concordance. We observed 1,074 synthetic events and 526 censored cases. In-sample concordance was 0.624 and independent synthetic holdout concordance 0.595. These describe only the invented experiment; they do not establish Everpure predictive quality.
>
> The second lane uses the approved Phase 1 account outputs. It reconciles all 2,000 accounts: 1,144 have source-reported inactivity of at least two years, 562 conflict with the calendar proxy, and 294 have unknown reported inactivity. The 1,144 form a provisional scenario cohort, not confirmed fiscal-year eligibility. One-to-one joins preserve account and root grain. Unknown health, ownership, and ticket values remain flagged. Scoring gives them explicit reference-level contributions; ticket code 999 remains missing in the source, while actual zero tickets stays zero. I exclude booking dates, account arithmetic, discount tier, historical spend, and reported inactivity amount from the hazard predictor.
>
> The account probabilities come from a versioned assumption register, not from the synthetic Cox fit. I selected conservative, base, and optimistic baseline hazards of 0.006, 0.012, and 0.020 per continuous month, with common modest effects for health, partner ownership, valid tickets, and child position. At the frozen October 9, 2026 origin, each probability is one minus exponential survival over a chosen horizon. In the base scenario, summing 1,144 account probabilities gives 33.672 expected reactivations by 3 months, 66.330 by 6, and 128.724 by 12. These are conditional expectations, not observed customers, campaign uplift, revenue, or NPV.
>
> Sensitivity varies hazards and effects on the same cohort, then separately expands the cohort to 1,706 and 2,000 hypothetical accounts. This separates changes in mean probability from a larger denominator. The full tests check source integrity, censoring semantics, numeric bounds, account grain, ordering, reconciliation, repeatability, and the isolation of the two lanes. Phase 3 receives a machine-readable probability contract that says the values are uncalibrated assumptions and specifies the missing financial inputs. To estimate real Everpure hazards, we would need timestamped dormant-cohort entry, observed reactivation events, censoring endpoints, pre-event covariates, and real held-out follow-up.
