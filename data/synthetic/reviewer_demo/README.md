# SYNTHETIC REVIEWER DEMONSTRATION — INVENTED ACCOUNTS, NOT EVERPURE DATA

`accounts.csv` holds 22 invented rows in the exact 12-column schema of the assessment
source, so the frozen production code can run end to end without the confidential file.
Every identifier starts with `SYN_`; no row was sampled, copied or derived from the
supplied Everpure dataset, and none of the values describe a real customer.

The rows are hand-designed to exercise each data-quality rule and routing branch:

| Injected condition | Rows |
|---|---|
| Duplicate account ID (exact duplicate row) | `SYN_C08` ×2 |
| Child whose parent is absent | `SYN_C16` → `SYN_R99` |
| Region whitespace / casing variants | `EMEA - France `, `emea - france`, `amer - us east `, … |
| Missing SFDC health as `nan` / `Missing` | `SYN_C02`, `SYN_C05`, `SYN_C07`, `SYN_C11`, `SYN_C14` |
| NaN partner-managed flag | `SYN_C03`, `SYN_R03`, `SYN_C14` |
| Sentinel `999` open tickets | `SYN_C05`, `SYN_C10` |
| Reported inactivity below two years (conflict) | `SYN_C09` |
| Reported inactivity missing (unknown) | `SYN_C11` |
| Usage exactly at the 37,656 GB scale cut / missing usage | `SYN_C13` / `SYN_C15` |

Reported `years_inactive` equals the booking-date gap to 2026-10-09 except for the
deliberate conflict and unknown rows. Run the demonstration with
`notebooks/00_synthetic_reviewer_demo.ipynb` or `everpure_case.reviewer_demo.run_reviewer_demo`.
Its outputs carry the label above and must never be presented as Everpure results.
