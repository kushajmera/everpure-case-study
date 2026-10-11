# Phase 3 financial scenario methodology

## Identification and population

This is an **illustrative financial scenario simulation, not an empirically calibrated revenue forecast**. The 2,000-row source contains no observed reactivation event, treatment assignment, post-reactivation revenue, margin, retention, or campaign cost. The Phase 2 primary cohort is 1,144 accounts with source-reported inactivity of at least two years. Its fiscal-year eligibility is unconfirmed. The 562 source/date eligibility conflicts and 294 unknown records remain outside the primary financial population. Historical recorded spend has an unknown period and unresolved hierarchy accounting; it never sets future monthly revenue.

The Phase 1 SHA-256, Phase 2 contract, probability and summary SHA-256, complete assumption fingerprint, Phase 2 formula, and 3/6/12-month expected event totals are checked before simulation. Source account rows are used only in local calculations. The synthetic Cox lane is excluded.

## Event generation and paired scenarios

For account $i$ and hazard scenario $s$, the assumed constant monthly hazard is $h_{is}=\lambda_s\exp(\eta_i)$. Phase 2 supplies $\eta_i$ and baseline hazards 0.006, 0.012, 0.020 per continuous month. The first-event CDF is $F_{is}(t)=1-\exp(-h_{is}t)$. A seeded NumPy PCG64 generator produces a 1,000 by 1,144 matrix of independent uniform draws. Open-interval clipping protects the inverse transform, $T_{isk}=-\log(1-U_{ik})/h_{is}$. A zero hazard gives infinity in isolated tests.

Accounts are sorted by account ID and root ID. One uniform per account and replication is reused across hazard cases. Each hazard case's event-time matrix is reused across its 5%, 15%, and 30% customer price tiers. Thus replications within a cell are independent under the conditional-independence assumption, while matching replication numbers across cells are intentionally paired. Shared uniforms imply $T_{optimistic}\le T_{base}\le T_{conservative}$. A single event time creates all cumulative horizon indicators; month-3, month-6 and month-12 counts are never added.

Root group dependence is unknown. The primary model assumes independent account draws conditional on hazards. This affects simulated portfolio variance and downside probability. It does not affect the sum of marginal analytical expectations if account marginal hazards stay fixed. No root correlation is estimated.

## Cash flows and NPV

The origin is model month zero, labeled 2026-10-09. A model month is a continuous abstract unit; no exact calendar deadline is asserted. Billing period $m$ is $(m-1,m]$. Revenue is earned only if $T_i\le m-1$, meaning a complete service period is available, and collected at its month-end $m$. There is no partial-month billing. Someone reactivating after month 11 may count as an event through month 12 while producing no paid service month in that horizon. Retention through the horizon is assumed. Ongoing servicing costs are contained in the 60% contribution margin.

At every eligible month, gross revenue is the illustrative $1,000 per account. Customer price discount $d$ yields $(1-d)$ times gross recognized revenue; contribution is then 60% of that amount. Costs contained within the remaining 40% of revenue therefore scale with commercially discounted revenue in the primary model. A fixed servicing-cost model could materially change the comparison, especially for deeper price discounts; the source cannot identify either cost structure. Every targeted account incurs $100 outreach at $t=0$. A first event at $T_i\le12$ incurs a single $200 activation cost discounted at that exact event time. An event later than month 12 creates no modeled activation cost or revenue. The annual effective financial rate is 12%; a payment at continuous month $t$ has factor $(1.12)^{-t/12}$. This financial discount is distinct from the customer's commercial price discount.

For replication $k$, $NPV_k=\sum_{m=1}^{12}Contribution_{km}DF(m)-\sum_{i:T_{ik}\le12}200DF(T_{ik})-1144(100)$. Month-zero and months 1 through 12 in `monthly_cashflow_summary.csv` sum to the run mean NPV. Gross revenue, commercial price deductions, contribution, nominal costs, present-value costs, and NPV are reported separately. This is **illustrative net program NPV, not causally attributed incremental campaign NPV**: no untreated counterfactual or discount response is identified.

## Independent analytical oracle

The simulation is checked against a closed-form expectation calculated directly from Phase 2 hazards, with no random event draws. For each account, expected present-value contribution is

$$R(1-d)M\sum_{m=1}^{12}DF(m)[1-\exp(-h_i(m-1))].$$

The expected present value of activation cost is $C_a\frac{h_i}{h_i+q}[1-\exp(-(h_i+q)12)]$ where $q=\log(1+r)/12$. The zero-hazard boundary is zero; the zero-financial-rate boundary uses $q=0$. Expected account NPV subtracts $C_o$. Account expectations sum to portfolio expected NPV. Each cell reports the finite Monte Carlo mean, sample standard deviation, standard error, and $z=(MC-analytic)/SE$. A predeclared absolute $z\le4.5$ is a conservative nine-cell diagnostic; it is not a proof of parameter validity. The nine comparisons are paired, so their $z$ scores are correlated. P5–P95 are conditional **outcome quantiles**, not confidence intervals for Everpure value.

## Sensitivity and break-even

One-at-a-time analytical sensitivities alter monthly gross revenue, margin, outreach and activation costs, annual financial rate, offered discount, hazard multiplier, and capped post-event paid months. The primary 1,000-run distribution is unchanged. Break-even thresholds solve the analytic NPV formula for revenue, margin, outreach or activation cost. The deeper-discount response calculation uses a separate hypothetical multiplier on each account's hazard and bisection in [1,100], targeting the base-hazard 5% offer's analytical NPV. The source gives no basis to assert that a price cut changes hazards, or to choose an optimal offer.

## Reproduction and controls

From the repository root with Python 3.12 and dependencies installed:

```powershell
$env:PYTHONPATH='src'
python -m everpure_case.source_integrity --repo-root .
python -m everpure_case.phase3_pipeline --repo-root .
python scripts/build_phase3_notebook.py
$env:EVERPURE_SANDBOX_JUPYTER='1'  # only if Windows sandbox requires it
python scripts/verify_phase3_notebook.py
python -m pytest -q -p no:cacheprovider -W error
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
```

The original assessment package was externally located and page 2 verified. It explicitly requests 1,000 Monte Carlo runs across three discount scenarios, without prescribing the financial inputs or offer percentages. The source's existing `discount_tier_pct` attribute spans 5%–65%, with a 34.9% mean in the provisional primary cohort; it is not a measured treatment response. The 5%/15%/30% offers are analyst-selected hypothetical prices.

The complete numerical and temporal defaults, provenance, and SHA-256 fingerprint are in `PHASE_3_FINANCIAL_ASSUMPTIONS.json`. Phase 3 CSVs serialize binary64 floats with 17 significant digits. Account and portfolio CSV reconciliations use `min($0.001, $1e-8 + 2e-12 × scale)` absolute tolerance, large enough for CSV round-trip and floating sums but below one cent. Output CSVs and JSONs are in `outputs/phase3`; `manifest.json` hashes each aggregate root file without a circular self-hash. The account-level handoff is explicitly Git-ignored at `outputs/phase3/local_only/account_economic_signals.csv`. `validate_phase3_artifacts(repo_root, mode="handoff")` is the read-only Phase 4 input boundary; `mode="complete"` additionally requires the notebook and six figures. Manifest consistency is not authenticity if an attacker can rewrite both data and manifest. The validator also recomputes an independent analytical account and portfolio oracle. Before any commit, inspect the full proposed file inventory for source IDs and confidentiality.
