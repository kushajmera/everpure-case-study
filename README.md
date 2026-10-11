# Everpure — Case Study 1: Reactivating Long-Dormant Accounts

Technical package for the **Install Base Monetization** case study. The submitted document is
[`deliverables/Everpure_Case_Study_Final_Submission.pdf`](deliverables/Everpure_Case_Study_Final_Submission.pdf):
five executive slides followed by a technical appendix. This repository holds the executable
evidence behind it: Python and DuckDB SQL source, Jupyter notebooks, tests, methodology
documentation and frozen aggregate results.

- Executable code and notebooks (this repository): https://github.com/kushajmera/everpure-case-study
- Full analytical evidence and diagrams (Google Drive): https://drive.google.com/drive/folders/1Ixur5zMZVuDybzTabTmsl3SsbrRX-Xts?usp=sharing

> **Data-use boundary.** The confidential assessment CSV, every account identifier, root mapping and
> account-level model output are deliberately excluded. See [DATA_USE_NOTICE.md](DATA_USE_NOTICE.md).
> A reviewer without the original file can still run the full workflow on invented accounts (Path B).

## Results at a glance (frozen, aggregate-only)

| Measure | Value | Basis |
|---|---:|---|
| Source accounts / roots / children | 2,000 / 301 / 1,699 | Observed source |
| Data-quality exception events | 4,889 across 1,968 accounts | Observed source |
| Provisionally two-year inactive (modeled) | 1,144 (57.2%) in 295 root groups | Source-reported `years_inactive` ≥ 2; fiscal eligibility unconfirmed |
| Excluded: inactivity conflicts / unknown | 562 / 294 | Held for review |
| Expected first reactivations within 12 months | 66.33 / 128.72 / 206.21 | Assumption-based hazards (conservative / base / optimistic) |
| Analytical expected net program NPV, base hazard | $241,533 / $201,502 / $141,454 | 5% / 15% / 30% hypothetical offers; illustrative unit economics |
| Monte Carlo, base / 15%, 1,000 runs | mean $202,912; P5 $150,709; P95 $256,482 | Conditional simulation percentiles |
| Committed combined adverse stress | −$124,647.43 | Separate alternative vector: −$124,704.05 |
| Planning routes (partner / direct / digital / hold) | 247 / 66 / 205 / 626 | Policy v2; planning only |
| Authorized customer-contact actions | 0 | `execution_authorized = false` for every account |

The financial values are **illustrative net program NPV, not causally attributed** and not verified
profitability. Reactivation probabilities are **assumption-based, not calibrated** to observed outcomes.

## Path B — run the synthetic demonstration (no confidential data)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/verify_reviewer_demo_notebook.py      # executes notebooks/00 in a fresh kernel
python -m pytest -q -p no:cacheprovider               # source-dependent tests skip automatically
```

`notebooks/00_synthetic_reviewer_demo.ipynb` runs the **frozen production code** on 22 invented `SYN_`
accounts: the Phase 1 orchestrator (cleaning, duplicate detection, region normalization, unknown
health, sentinel tickets, arbitrary-depth hierarchy), DuckDB SQL with CTEs, `LAG`/`LEAD`/`DENSE_RANK`
and running windows, the synthetic Cox model, assumed-hazard probabilities, closed-form and Monte
Carlo NPV across three discount tiers, and the GTM routing rules with root coordination and the
authorization gate. It demonstrates mechanics only and never reproduces Everpure results.

## Path A — authorized full reproduction (requires the original assessment CSV)

Place the supplied file at `data/raw/Case_Study_1_Install_Base_Reactivation.csv`. The integrity gate
checks SHA-256 `6863ea0014f050355bf9e0c5166e2284edfe8521ea3d87a2a2fa168177a229bc`, 2,000 rows and $2,541,024,291 recorded spend before anything runs.

```bash
python -m pip install -r requirements.txt
export PYTHONPATH=src            # PowerShell: $env:PYTHONPATH='src'
python -m everpure_case.source_integrity --repo-root .
python -m everpure_case.pipeline --repo-root . --as-of 2026-10-09
python scripts/build_notebook.py && python scripts/verify_notebook.py
python -m everpure_case.phase2_pipeline --repo-root .
python scripts/build_phase2_notebook.py && python scripts/verify_phase2_notebook.py
python -m everpure_case.phase3_pipeline --repo-root .
python scripts/build_phase3_notebook.py && python scripts/verify_phase3_notebook.py
python scripts/build_phase4_notebook.py
python -m everpure_case.phase4_pipeline --repo-root .
python scripts/verify_phase4_notebook.py
python -m pytest -q -p no:cacheprovider -W error
```

Run the steps in this order: each phase validates the previous phase's manifest and fingerprints,
and the Phase 3 manifest is complete only after its notebook verifier records the notebook and
figures. The pipelines regenerate the git-ignored account-level files locally and re-derive every
committed aggregate; the validators reject any drift. Notebook 01 is shipped without outputs
because its executed form displays source rows; keep the executed copy local. On a constrained
Windows sandbox the notebook verifiers may need `EVERPURE_SANDBOX_JUPYTER=1`.

## Repository map

| Path | Contents |
|---|---|
| `notebooks/` | `00` synthetic end-to-end demo (executed) · `01` data foundation & SQL · `02` survival · `03` Monte Carlo NPV · `04` GTM routing |
| `src/everpure_case/` | Source integrity, cleaning, hierarchy, SQL runner, survival, scenarios, financial model, routing policy and rules |
| `sql/` | DuckDB SQL: hierarchy roll-ups, spend concentration, regional spend, account features, synthetic decay velocity |
| `tests/` | pytest suite; tests that need the confidential CSV skip when it is absent (`conftest.py`) |
| `docs/` | Methodology, results, assumption registers, data contracts, routing policy, decision table and flowchart |
| `outputs/` | Frozen aggregate results and SHA-256 manifests for Phases 1–4 (no account-level rows) |
| `data/synthetic/` | Invented fixtures for the decay SQL and the reviewer demonstration |
| `scripts/phase5/` | Submission build: validated inputs, PDF builder and release gate, this package builder |
| `deliverables/` | The submitted PDF |

## Provenance

| Artifact | SHA-256 |
|---|---|
| Source CSV (not included) | `6863ea0014f050355bf9e0c5166e2284edfe8521ea3d87a2a2fa168177a229bc` |
| Phase 2 assumption register | `6195ba2e90c95976ed91b7bdd42509341fd22e71e6b2bb5aed2e5d2a6d346ee7` |
| Phase 3 financial assumptions | `b953c02d3fdcfacc62d9e6755889040e9f8bd12db7c830a88c79f5c991267e70` |
| Phase 4 routing policy | `1998cc4a68c88160f01d89ca0abfe7c2ae955d912181b872556c149e5201af3c` |
| Phase 5 input contract | `89bfe72319e31112fa64b837b741e664278ab919d45c8f6ad3614adc2613398a` |

Every file in this package is listed with its SHA-256 in [`PUBLICATION_MANIFEST.json`](PUBLICATION_MANIFEST.json).
This repository was created with a fresh history containing only these reviewed files.
