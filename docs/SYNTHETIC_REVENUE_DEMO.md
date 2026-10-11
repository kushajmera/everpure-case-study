# SYNTHETIC METHODOLOGY DEMONSTRATION — NOT OBSERVED EVERPURE REVENUE

This is an executable SQL example, **separate from the authoritative account CSV**. Run `python -m everpure_case.synthetic_demo --repo-root .` after installing the package. It reads only [data/synthetic](../data/synthetic/README.md) and writes only [outputs/phase1/synthetic_demo](../outputs/phase1/synthetic_demo/). The real Phase 1 pipeline never joins these observations to Everpure accounts, totals, or opportunity rankings.

The fixture CSVs have no label column. Their provenance is established by the isolated directory, its README, and `SYN_` identifiers; generated CSVs and the manifest contain the explicit demonstration label. Before DuckDB runs, `validate_fiscal_calendar` requires unique, consecutive indices in row order and strictly increasing valid period-end dates. A missing calendar period is an error. A missing *account observation* within a valid calendar remains missing and is never silently treated as zero.

## Defined grain and consolidation assumption

- [hierarchy.csv](../data/synthetic/hierarchy.csv): five invented accounts in two roots, including two children under `SYN_R1`. `resolve_hierarchy` validates a one-to-one account-to-root mapping before SQL runs.
- [fiscal_calendar.csv](../data/synthetic/fiscal_calendar.csv): four ordered, invented fiscal quarters. `fiscal_period_index` is the elapsed-period unit; the calendar dates are fixture labels, **not** a claim about Everpure's fiscal calendar.
- [account_period_revenue.csv](../data/synthetic/account_period_revenue.csv): 19 invented account × period revenue observations. `SYN_B` lacks period 3; `SYN_C` has a recorded zero in period 1. Those states are intentionally different.
- **Synthetic-only consolidation rule:** a root's own period revenue excludes its children's revenue. Summing one observation per account within a root is therefore valid *for this fixture only*. No such rule is available for the real `historical_spend_usd` field.

## Account calculation

[synthetic_account_decay.sql](../sql/synthetic_account_decay.sql) uses `validated` and `sequenced` CTEs, a deterministic hierarchy join, and `LAG`/`LEAD` within each account. `DENSE_RANK` orders each account's observed periods newest first. For observed current and previous rows:

- `elapsed_periods = current_period_index - previous_period_index`.
- `absolute_change_usd = current_revenue - previous_revenue`; this is an **across-observation** change when a gap exists.
- `consecutive_pct_change = absolute_change_usd / previous_revenue` **only if** `elapsed_periods = 1` and previous revenue is nonzero. This is dimensionless quarter-over-quarter change, not an unqualified “velocity.”
- `signed_change_usd_per_period = absolute_change_usd / elapsed_periods`. Its units are USD per fixture fiscal period. A negative value indicates decline; a positive value indicates increase. Across a gap, it is a multi-period average, **not** an ordinary single-quarter change.

| Invented account observation | Previous → current USD | Elapsed periods | Absolute change USD | Consecutive percent | Signed USD/period | Status |
|---|---:|---:|---:|---:|---:|---|
| `SYN_A`, period 2 | 100 → 80 | 1 | -20 | -20% | -20 | `consecutive` |
| `SYN_B`, period 4 | 50 → 70 | 2 | +20 | null | +10 | `nonconsecutive_gap` |
| `SYN_C`, period 2 | 0 → 20 | 1 | +20 | null | +20 | `consecutive_zero_baseline` |

`SYN_B` period 3 is **missing**, not zero. `SYN_C` period 1 is **observed zero**. The guarded zero baseline never yields infinity; the absolute USD change remains available.

## Root calculation

[synthetic_root_decay.sql](../sql/synthetic_root_decay.sql) groups account observations at root × period before taking period changes. A root × calendar grid compares the number of observed account rows with its expected member count. An incomplete period retains `observed_partial_revenue_usd` for audit but sets `root_revenue_usd` to null. Root changes require both current and preceding calendar periods to be complete. `DENSE_RANK` ranks only complete root totals within a period; incomplete roots receive null rank.

| Invented root | Period | Observed / expected members | Partial sum USD | Complete root USD | Consecutive change USD | Interpretation |
|---|---:|---:|---:|---:|---:|---|
| `SYN_R1` | 1 | 3 / 3 | 150 | 150 | null | First period: 0 + 100 + 50. |
| `SYN_R1` | 2 | 3 / 3 | 130 | 130 | -20 | (130 - 150) / 150 = -13.3333%; -20 USD/period. |
| `SYN_R1` | 3 | 2 / 3 | 60 | null | null | `SYN_B` missing; 60 is incomplete, **not** root revenue. |
| `SYN_R1` | 4 | 3 / 3 | 110 | 110 | null | Previous calendar period incomplete; ordinary QoQ change suppressed. |
| `SYN_R2` | 2 | 2 / 2 | 220 | 220 | +20 | 200 root + 20 child; +10% versus period 1. |

The [executed account output](../outputs/phase1/synthetic_demo/synthetic_account_decay.csv), [root output](../outputs/phase1/synthetic_demo/synthetic_root_decay.csv), and [manifest](../outputs/phase1/synthetic_demo/manifest.json) each carry the synthetic demonstration label or provenance. [test_synthetic_demo.py](../tests/test_synthetic_demo.py) compares SQL output against independently written expected values, including the missing period, zero baseline, and root rollup.

The Everpure CSV has no account-period revenue, so **none of these invented values estimates real revenue decay**. The [longitudinal template](../sql/longitudinal_decay_template.sql) remains an unexecuted interface for future *real* account-period data. It now requires an indexed fiscal calendar and guards gaps and zero baselines; this controlled demonstration supplies testable execution evidence without pretending the source has such observations.
