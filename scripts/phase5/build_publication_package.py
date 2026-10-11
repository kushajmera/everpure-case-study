"""Assemble the sanitized, allowlisted GitHub publication package and scan it.

The package is copied file by file from an explicit allowlist. It never copies the
development ``.git`` directory, checkpoint refs, the raw assessment CSV, git-ignored
account-level outputs or local runtime directories. A fresh, independent Git history is
created separately with ``--git-init`` only after the scans pass. Nothing is pushed.
"""

# ruff: noqa: E501  # Long README and notice strings.

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import submission_config as cfg  # noqa: E402
from phase5_inputs import FROZEN, ROOT  # noqa: E402

PACKAGE = ROOT / "submission/publication_package"
MARKER = "PUBLICATION_MANIFEST.json"

# Tracked-file globs that are approved for publication (all aggregate-only or code).
TRACKED_ALLOW = [
    ".gitattributes",
    "pyproject.toml",
    "src/everpure_case/*.py",
    "sql/*.sql",
    "scripts/*.py",
    "tests/*.py",
    "docs/*",
    "data/synthetic/*",
    "notebooks/02_survival_analysis.ipynb",
    "notebooks/03_monte_carlo_npv.ipynb",
    "notebooks/04_gtm_routing.ipynb",
    "outputs/phase1/*.csv",
    "outputs/phase1/synthetic_demo/*",
    "outputs/phase2/*",
    "outputs/phase2/figures/*",
    "outputs/phase3/*",
    "outputs/phase3/figures/*",
    "outputs/phase4/*",
]
# New Phase 5 files (untracked in the development repository until authorized).
PHASE5_FILES = [
    "src/everpure_case/reviewer_demo.py",
    "tests/test_reviewer_demo.py",
    "scripts/build_reviewer_demo_notebook.py",
    "scripts/verify_reviewer_demo_notebook.py",
    "notebooks/00_synthetic_reviewer_demo.ipynb",
    "data/synthetic/reviewer_demo/accounts.csv",
    "data/synthetic/reviewer_demo/README.md",
    "scripts/phase5/phase5_inputs.py",
    "scripts/phase5/submission_config.py",
    "scripts/phase5/build_submission_pdf.py",
    "scripts/phase5/validate_submission_pdf.py",
    "scripts/phase5/build_publication_package.py",
    "scripts/phase5/build_drive_evidence.py",
    "scripts/phase5/build_submission_pptx.py",
    "scripts/phase5/pptx_kit.py",
]
DELIVERABLES = {
    "submission/Everpure_Case_Study_Final_Submission.pdf": "deliverables/Everpure_Case_Study_Final_Submission.pdf",
    "submission/Everpure_Executive_Presentation.pptx": "deliverables/Everpure_Executive_Presentation.pptx",
}
NEVER = [
    r"(^|/)\.git(/|$)",
    r"(^|/)\.runtime(/|$)",
    r"__pycache__",
    r"\.ruff_cache",
    r"pytest-tmp",
    r"local_only",
    r"^data/raw/",
    r"_scratch_",
    r"\.ipynb_checkpoints",
]
# Tests that read the confidential source or its git-ignored derivatives.
SOURCE_DEPENDENT_TESTS = [
    "test_pipeline.py",
    "test_source_integrity.py",
    "test_phase2_pipeline.py",
    "test_reactivation_scenarios.py",
    "test_phase3_financial.py",
    "test_phase4_routing.py",
]

SECRET_PATTERNS = [
    r"ghp_[A-Za-z0-9]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"(?i)(api[_-]?key|secret[_-]?key|password)\s*[:=]\s*['\"][^'\"]{6,}",
]
# Generic local-path patterns, written so none of them matches its own source text.
GENERIC_PRIVATE_PATTERNS = [
    r"(?i)[A-Z]:\\+Users\\+",
    r"(?i)[A-Z]:[/]Users[/]",
    r"(?i)[/]Users[/]",
    r"App[D]ata",
]
# Simulated portfolio totals that coincide numerically with round recorded-spend values;
# reviewed: no account dimension (columns contribution, discounted revenue, net cash flow).
SPEND_COLLISION_REVIEWED = {"outputs/phase3/monte_carlo_run_results.csv"}


def private_tokens() -> list[str]:
    """Environment-specific strings that must never be published, derived at runtime.

    They are the local account name, the development remote's owner when it differs from
    the publication owner, and every non-standard ref namespace (for example checkpoint
    refs). Deriving them keeps the literals out of every published file, including this one.
    """
    tokens = {Path.home().name}
    git = ["git", "-C", str(ROOT)]
    remote = subprocess.run([*git, "remote", "get-url", "origin"], capture_output=True, text=True)
    match = re.search(r"github\.com[/:]([^/]+)/", remote.stdout)
    publication_owner = re.search(r"github\.com/([^/]+)/", cfg.GITHUB_URL).group(1)
    if match and match.group(1) != publication_owner:
        tokens.add(match.group(1))
    refs = subprocess.run(
        [*git, "for-each-ref", "--format=%(refname)"], capture_output=True, text=True
    ).stdout.split()
    for ref in refs:
        parts = ref.split("/")
        if len(parts) > 2 and parts[1] not in {"heads", "tags", "remotes", "stash"}:
            tokens.add("/".join(parts[:2]))
    return sorted(t for t in tokens if len(t) >= 4)


PRIVATE_PATTERNS = GENERIC_PRIVATE_PATTERNS + [re.escape(t) for t in private_tokens()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"], check=True, capture_output=True, text=True
    ).stdout.splitlines()
    return out


def select_files() -> list[str]:
    tracked = tracked_files()
    chosen = set()
    for pattern in TRACKED_ALLOW:
        regex = re.compile("^" + re.escape(pattern).replace(r"\*", "[^/]+") + "$")
        chosen.update(path for path in tracked if regex.match(path))
    chosen.update(PHASE5_FILES)
    for path in list(chosen):
        if any(re.search(rule, path) for rule in NEVER):
            chosen.discard(path)
    missing = [p for p in chosen if not (ROOT / p).is_file()]
    if missing:
        raise SystemExit(f"Allowlisted files are missing: {missing}")
    return sorted(chosen)


README = """# Everpure — Case Study 1: Reactivating Long-Dormant Accounts

Technical package for the **Install Base Monetization** case study. The submitted document is
[`deliverables/Everpure_Case_Study_Final_Submission.pdf`](deliverables/Everpure_Case_Study_Final_Submission.pdf):
five executive slides followed by a technical appendix. This repository holds the executable
evidence behind it: Python and DuckDB SQL source, Jupyter notebooks, tests, methodology
documentation and frozen aggregate results.

- Executable code and notebooks (this repository): {github}
- Full analytical evidence and diagrams (Google Drive): {drive}

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
# Windows: .venv\\Scripts\\activate     macOS/Linux: source .venv/bin/activate
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
checks SHA-256 `{source_sha}`, 2,000 rows and $2,541,024,291 recorded spend before anything runs.

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
| Source CSV (not included) | `{source_sha}` |
| Phase 2 assumption register | `{p2}` |
| Phase 3 financial assumptions | `{p3}` |
| Phase 4 routing policy | `{p4}` |
| Phase 5 input contract | `{p5}` |

Every file in this package is listed with its SHA-256 in [`PUBLICATION_MANIFEST.json`](PUBLICATION_MANIFEST.json).
This repository was created with a fresh history containing only these reviewed files.
"""

NOTICE = """# Data-use notice

This repository accompanies a candidate submission for the Everpure FY27 internship assessment,
Case Study 1. It is shared so reviewers can inspect and execute the analysis code.

- **Assessment data is not redistributed.** The supplied `Case_Study_1_Install_Base_Reactivation.csv`,
  the assessment brief, and every file derived from them at account level (cleaned rows, account
  identifiers, parent-child mappings, exception registers, account-level probabilities, economics
  and routing decisions) are excluded. Nothing here grants any right to the assessment materials.
- **Committed results are aggregate-only.** Files under `outputs/` contain cohort-level counts,
  scenario totals, simulation summaries and synthetic methodology outputs, each listed in a
  SHA-256 manifest.
- **Synthetic data is invented.** Everything under `data/synthetic/` uses `SYN_` identifiers created
  for demonstration; no row is sampled from or derived from the assessment source.
- **Results are illustrative.** Reactivation probabilities are assumption-based, financial values
  are illustrative net program NPV without causal attribution, and every GTM route is planning-only
  with no customer-contact authorization.
- **No license is granted for third-party data.** Code is provided for assessment review.
"""

GITIGNORE = """__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.ipynb_checkpoints/
.venv/
.runtime/
*.egg-info/
tests/_scratch_*/
outputs/*/pytest-tmp/
outputs/*/local_only/
# The confidential assessment CSV and every account-level derivative stay local.
data/raw/
outputs/phase1/cleaned_accounts.csv
outputs/phase1/account_opportunity.csv
outputs/phase1/account_hierarchy.csv
outputs/phase1/account_quality_summary.csv
outputs/phase1/data_quality_exceptions.csv
outputs/phase1/direct_child_counts.csv
outputs/phase1/hierarchy_exceptions.csv
outputs/phase1/hierarchy_sql_summary.csv
outputs/phase1/parent_child_spend_comparison.csv
outputs/phase1/parent_spend_summary.csv
outputs/phase1/spend_concentration.csv
outputs/phase1/window_analytics.csv
outputs/phase1/metrics.json
outputs/phase2/reactivation_scenario_probabilities.csv
outputs/phase2/cohort_reconciliation.csv
.env
.env.*
*.pem
*.key
"""

CONFTEST = '''"""Skip tests that need the confidential assessment CSV when it is not present (Path B)."""

from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parent / "data/raw/Case_Study_1_Install_Base_Reactivation.csv"
SOURCE_DEPENDENT = {modules}
SOURCE_DEPENDENT_TESTS = {{"test_sql_and_pandas_group_totals_match_for_actual_source"}}


def pytest_collection_modifyitems(config, items):
    if SOURCE.is_file():
        return
    skip = pytest.mark.skip(reason="requires the confidential assessment CSV (README Path A)")
    for item in items:
        if (
            Path(str(item.fspath)).name in SOURCE_DEPENDENT
            or "isolated_repo" in getattr(item, "fixturenames", ())
            or item.originalname in SOURCE_DEPENDENT_TESTS
        ):
            item.add_marker(skip)
'''

REQUIREMENTS = """# Tested with Python 3.12.10 on Windows 11 (2026-10-11).
pandas==2.2.3
numpy==2.2.6
duckdb==1.5.6
matplotlib==3.10.3
lifelines==0.30.3
scipy==1.18.1
nbformat==5.11.1
nbclient==0.11.0
ipykernel==7.4.0
pytest==9.0.3
"""


def build() -> dict:
    if PACKAGE.exists():
        if not (PACKAGE / MARKER).is_file() and any(PACKAGE.iterdir()):
            raise SystemExit(f"Refusing to replace unexpected directory {PACKAGE}")
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    files = select_files()
    for rel in files:
        target = PACKAGE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
    for src, dst in DELIVERABLES.items():
        target = PACKAGE / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / src, target)
    (PACKAGE / "README.md").write_text(
        README.format(
            github=cfg.GITHUB_URL,
            drive=cfg.DRIVE_URL,
            source_sha=FROZEN["source_sha256"],
            p2=FROZEN["phase2_assumption_fingerprint"],
            p3=FROZEN["phase3_financial_fingerprint"],
            p4=FROZEN["phase4_policy_fingerprint"],
            p5=FROZEN["phase5_contract_sha256"],
        ),
        encoding="utf-8",
    )
    (PACKAGE / "DATA_USE_NOTICE.md").write_text(NOTICE, encoding="utf-8")
    (PACKAGE / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (PACKAGE / "requirements.txt").write_text(REQUIREMENTS, encoding="utf-8")
    (PACKAGE / "conftest.py").write_text(
        CONFTEST.format(
            modules="{\n" + "".join(f'    "{m}",\n' for m in sorted(SOURCE_DEPENDENT_TESTS)) + "}"
        ),
        encoding="utf-8",
    )
    # Notebook 01 ships source-only: its executed form displays source rows.
    subprocess.run(
        [sys.executable, str(PACKAGE / "scripts/build_notebook.py")],
        check=True,
        capture_output=True,
    )
    return scan_and_manifest()


def extract_text(data: bytes) -> str:
    """Raw text plus the decoded members of ZIP containers (PPTX, XLSX), recursively."""
    import io

    text = data.decode("utf-8", errors="ignore")
    if data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for member in archive.namelist():
                    text += " " + extract_text(archive.read(member))
        except zipfile.BadZipFile:
            pass
    return text


def _source_identifiers() -> tuple[set[str], set[str]]:
    path = ROOT / "data/raw/Case_Study_1_Install_Base_Reactivation.csv"
    ids, spends = set(), set()
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            ids.add(row["account_id"].strip())
            if row["parent_account_id"].strip():
                ids.add(row["parent_account_id"].strip())
            spends.add(row["historical_spend_usd"].strip())
    return ids, spends


def scan_and_manifest() -> dict:
    ids, spends = _source_identifiers()
    id_regex = re.compile(r"ACC_\d+")
    spend_values = {s for s in spends if len(s.replace(".", "")) >= 6}
    findings: dict[str, list] = {
        "source_account_ids": [],
        "acc_pattern": [],
        "exact_source_spend_values": [],
        "secrets": [],
        "private_paths_or_refs": [],
        "forbidden_paths": [],
    }
    entries, reviewed = [], []
    all_files = sorted(p for p in PACKAGE.rglob("*") if p.is_file() and ".git" not in p.parts)
    for path in all_files:
        rel = path.relative_to(PACKAGE).as_posix()
        if rel == MARKER:
            continue
        if any(re.search(rule, rel) for rule in NEVER):
            findings["forbidden_paths"].append(rel)
        data = path.read_bytes()
        text = extract_text(data)
        if id_regex.search(text):
            findings["acc_pattern"].append(rel)
        hits = {i for i in id_regex.findall(text) if i in ids}
        if hits:
            findings["source_account_ids"].append([rel, sorted(hits)[:5]])
        if path.suffix in {".csv", ".json", ".md", ".ipynb", ".py", ".sql", ".txt"}:
            numbers = set(re.findall(r"(?<![\w.])\d{6,}(?:\.\d+)?(?![\w.])", text))
            spend_hits = sorted(numbers & spend_values)
            if spend_hits and rel not in SPEND_COLLISION_REVIEWED:
                findings["exact_source_spend_values"].append([rel, spend_hits[:5]])
            elif spend_hits:
                reviewed.append([rel, len(spend_hits)])
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text):
                findings["secrets"].append([rel, pattern])
        for index, pattern in enumerate(PRIVATE_PATTERNS):
            if re.search(pattern, text):
                findings["private_paths_or_refs"].append([rel, f"private pattern #{index}"])
        entries.append(
            {"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        )
    manifest = {
        "version": "everpure-publication-manifest-v1",
        "intended_repository": cfg.GITHUB_URL,
        "evidence_folder": cfg.DRIVE_URL,
        "source_sha256_not_included": FROZEN["source_sha256"],
        "development_baseline_commit": FROZEN["phase4_head"],
        "file_count": len(entries),
        "total_bytes": sum(e["bytes"] for e in entries),
        "files": entries,
    }
    (PACKAGE / MARKER).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {
        "manifest_sha256": sha256(PACKAGE / MARKER),
        "files": len(entries),
        "private_pattern_count": len(PRIVATE_PATTERNS),
        "reviewed_spend_collisions": reviewed,
        "findings": findings,
    }


def git_init() -> dict:
    if (PACKAGE / ".git").exists():
        raise SystemExit("Package already has a Git history; rebuild the package first")

    def run(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(PACKAGE), *args], check=True, capture_output=True, text=True
        ).stdout

    run("init", "-b", "main")
    run("add", "-A")
    message = (
        "Publish sanitized Everpure Case Study 1 technical package\n\n"
        "Fresh history containing only allowlisted, reviewed files: source, SQL, notebooks,\n"
        "tests, documentation, aggregate outputs and the submission PDF. The confidential\n"
        "assessment CSV and all account-level derivatives are excluded.\n\n"
        "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
    )
    run("commit", "-q", "-m", message)
    return {
        "head": run("rev-parse", "HEAD").strip(),
        "commits": run("rev-list", "--count", "HEAD").strip(),
        "refs": run("for-each-ref", "--format=%(refname)").split(),
        "remotes": run("remote").split(),
        "tracked_files": len(run("ls-files").splitlines()),
        "author": run("log", "-1", "--format=%an <%ae>").strip(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--git-init", action="store_true", help="create the fresh history")
    args = parser.parse_args()
    if args.git_init:
        print(json.dumps(git_init(), indent=2))
        return
    result = build()
    print(json.dumps(result, indent=2))
    problems = {k: v for k, v in result["findings"].items() if v}
    if problems:
        raise SystemExit(f"Publication scan FAILED: {sorted(problems)}")


if __name__ == "__main__":
    main()
