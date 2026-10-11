"""Stage the sanitized Google Drive evidence folder and its index (nothing is uploaded)."""

# ruff: noqa: E501  # Long index strings.

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import submission_config as cfg  # noqa: E402
from build_publication_package import (  # noqa: E402
    PRIVATE_PATTERNS,
    SECRET_PATTERNS,
    _source_identifiers,
    extract_text,
)
from phase5_inputs import FROZEN, ROOT  # noqa: E402

EVIDENCE = ROOT / "submission/drive_evidence_package"
PDF = ROOT / "submission/Everpure_Case_Study_Final_Submission.pdf"
INDEX = "00_START_HERE_EVIDENCE_INDEX.md"

DIAGRAM_PAGES = [  # (zero-based page, file name, description)
    (
        0,
        "Slide1_Opportunity_and_Recommendation.pdf",
        "Executive slide 1: cohort composition and gated recommendation",
    ),
    (
        1,
        "Slide2_Data_Foundation_and_Architecture.pdf",
        "Executive slide 2: hygiene scorecard and modeling architecture",
    ),
    (
        2,
        "Slide3_Survival_Scenarios.pdf",
        "Executive slide 3: Cox demonstration lane and assumed-hazard scenarios",
    ),
    (
        3,
        "Slide4_Monte_Carlo_NPV.pdf",
        "Executive slide 4: NPV by offer, Monte Carlo distribution, unit economics",
    ),
    (
        4,
        "Slide5_GTM_Routing_and_Decision.pdf",
        "Executive slide 5: routes, evidence quality, release gates",
    ),
    (
        8,
        "AppendixD_Nine_Cell_Monte_Carlo_Table.pdf",
        "All nine scenario × offer cells: analytical vs. simulated NPV",
    ),
    (
        9,
        "AppendixE_Sensitivity_and_Stress.pdf",
        "Sensitivity tornado, break-even and both adverse stress vectors",
    ),
    (
        10,
        "AppendixF_GTM_Routing_Flowchart.pdf",
        "Algorithmic GTM routing flowchart, rule order R0–R8 with counts",
    ),
]
TABLES = [
    "outputs/phase1/inactivity_reconciliation.csv",
    "outputs/phase1/analysis_date_sensitivity.csv",
    "outputs/phase1/regional_spend.csv",
    "outputs/phase2/reactivation_scenario_summary.csv",
    "outputs/phase2/scenario_sensitivity.csv",
    "outputs/phase2/synthetic_cox_coefficients.csv",
    "outputs/phase2/synthetic_model_diagnostics.json",
    "outputs/phase3/financial_scenario_matrix.csv",
    "outputs/phase3/monte_carlo_npv_summary.csv",
    "outputs/phase3/financial_sensitivity.csv",
    "outputs/phase3/discount_break_even.csv",
    "outputs/phase3/monthly_cashflow_summary.csv",
    "outputs/phase3/financial_reconciliation.json",
    "outputs/phase4/routing_channel_summary.csv",
    "outputs/phase4/routing_rule_counts.csv",
    "outputs/phase4/commercial_priority_summary.csv",
    "outputs/phase4/priority_evidence_summary.csv",
    "outputs/phase4/data_readiness_summary.csv",
    "outputs/phase4/service_barrier_summary.csv",
    "outputs/phase4/root_coordination_summary.csv",
    "outputs/phase4/cohort_reconciliation_summary.csv",
    "outputs/phase4/scenario_priority_sensitivity.csv",
    "outputs/phase4/metrics.json",
    "outputs/phase4/phase5_input_contract.json",
]
FIGURES = sorted(
    p.relative_to(ROOT).as_posix()
    for folder in ("outputs/phase2/figures", "outputs/phase3/figures")
    for p in (ROOT / folder).glob("*.png")
)
NOTEBOOKS = [
    "notebooks/00_synthetic_reviewer_demo.ipynb",
    "notebooks/02_survival_analysis.ipynb",
    "notebooks/03_monte_carlo_npv.ipynb",
    "notebooks/04_gtm_routing.ipynb",
]
DOCS = [
    "docs/PHASE_1_RESULTS.md",
    "docs/DATA_QUALITY.md",
    "docs/METHODOLOGY.md",
    "docs/PHASE_2_METHODOLOGY.md",
    "docs/PHASE_2_RESULTS.md",
    "docs/PHASE_2_ASSUMPTION_REGISTER.md",
    "docs/PHASE_3_METHODOLOGY.md",
    "docs/PHASE_3_RESULTS.md",
    "docs/PHASE_3_ASSUMPTION_REGISTER.md",
    "docs/PHASE_4_METHODOLOGY.md",
    "docs/PHASE_4_RESULTS.md",
    "docs/PHASE_4_DECISION_TABLE.md",
    "docs/PHASE_4_ROUTING_FLOWCHART.md",
    "docs/PHASE_4_ROUTING_POLICY.json",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    if EVIDENCE.exists():
        if not (EVIDENCE / INDEX).is_file():
            raise SystemExit(f"Refusing to replace unexpected directory {EVIDENCE}")
        shutil.rmtree(EVIDENCE)
    rows = []

    def add(src: Path, dest: str, kind: str, note: str) -> None:
        target = EVIDENCE / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        rows.append((dest, kind, note))

    add(
        PDF,
        "01_Submission/Everpure_Case_Study_Final_Submission.pdf",
        "Deliverable",
        "The submitted PDF: five executive slides plus technical appendix",
    )
    add(
        ROOT / "submission/Everpure_Executive_Presentation.pptx",
        "01_Submission/Everpure_Executive_Presentation.pptx",
        "Deliverable",
        "Editable five-slide executive deck (mirrors PDF pages 1-5)",
    )
    source = pymupdf.open(PDF)
    for page, name, note in DIAGRAM_PAGES:
        target = EVIDENCE / "02_Diagrams_vector" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        single = pymupdf.open()
        single.insert_pdf(source, from_page=page, to_page=page)
        single.set_metadata(
            {"title": f"{cfg.PDF_TITLE} — {note}", "author": "", "creator": "", "producer": ""}
        )
        single.save(target, garbage=4, deflate=True)
        rows.append((f"02_Diagrams_vector/{name}", "Diagram (vector page)", note))
    for rel in FIGURES:
        add(
            ROOT / rel,
            f"03_Aggregate_Figures/{Path(rel).name}",
            "Figure (aggregate or synthetic)",
            f"Frozen figure from {rel}",
        )
    for rel in TABLES:
        add(
            ROOT / rel,
            f"04_Result_Tables/{rel.split('/')[1]}__{Path(rel).name}",
            "Aggregate table",
            f"Frozen output {rel}",
        )
    for rel in NOTEBOOKS:
        add(
            ROOT / rel,
            f"05_Notebooks/{Path(rel).name}",
            "Notebook",
            "Synthetic, executed"
            if "00_" in rel
            else "Aggregate-only notebook from the frozen phase",
        )
    for rel in DOCS:
        add(ROOT / rel, f"06_Methodology/{Path(rel).name}", "Documentation", f"Frozen {rel}")

    entries = [
        {
            "path": dest,
            "classification": kind,
            "description": note,
            "bytes": (EVIDENCE / dest).stat().st_size,
            "sha256": sha256(EVIDENCE / dest),
        }
        for dest, kind, note in rows
    ]
    lines = [
        "# Everpure Case Study 1 — Full Analytical Evidence & Diagrams",
        "",
        "Supporting evidence for the submitted PDF. Everything here is aggregate-only, synthetic, or",
        "documentation; the confidential assessment CSV, account identifiers, parent-child mappings and",
        "account-level model outputs are deliberately excluded.",
        "",
        f"- Executable code, SQL and notebooks: {cfg.GITHUB_URL}",
        f"- This evidence folder: {cfg.DRIVE_URL}",
        f"- Source dataset fingerprint (file not included): SHA-256 `{FROZEN['source_sha256']}`",
        "",
        "Financial values are illustrative net program NPV under analyst-selected assumptions, not causal",
        "uplift or verified profit. Reactivation probabilities are assumption-based, not calibrated. All GTM",
        "routes are planning-only; zero customer-contact actions are authorized.",
        "",
        "| File | Type | What it shows | SHA-256 (first 16) |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| `{e['path']}` | {e['classification']} | {e['description']} | `{e['sha256'][:16]}` |"
        for e in entries
    ]
    (EVIDENCE / INDEX).write_text("\n".join(lines) + "\n", encoding="utf-8")
    (EVIDENCE / "EVIDENCE_MANIFEST.json").write_text(
        json.dumps(
            {
                "version": "everpure-drive-evidence-v1",
                "drive_folder": cfg.DRIVE_URL,
                "github_repository": cfg.GITHUB_URL,
                "files": entries,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return scan(entries)


def scan(entries: list[dict]) -> dict:
    ids, spends = _source_identifiers()
    findings: dict[str, list] = {
        "source_account_ids": [],
        "acc_pattern": [],
        "secrets": [],
        "private_paths_or_refs": [],
        "exact_source_spend_values": [],
    }
    spend_values = {s for s in spends if len(s.replace(".", "")) >= 6}
    for path in sorted(p for p in EVIDENCE.rglob("*") if p.is_file()):
        rel = path.relative_to(EVIDENCE).as_posix()
        if path.suffix == ".pdf":
            text = "\n".join(page.get_text() for page in pymupdf.open(path))
            text += path.read_bytes().decode("latin-1", errors="ignore")
        else:
            text = extract_text(path.read_bytes())
        if re.search(r"ACC_\d+", text):
            findings["acc_pattern"].append(rel)
        hits = {i for i in re.findall(r"ACC_\d+", text) if i in ids}
        if hits:
            findings["source_account_ids"].append([rel, sorted(hits)[:5]])
        if path.suffix in {".csv", ".json", ".md", ".ipynb"}:
            numbers = set(re.findall(r"(?<![\w.])\d{6,}(?:\.\d+)?(?![\w.])", text))
            if numbers & spend_values:
                findings["exact_source_spend_values"].append(
                    [rel, sorted(numbers & spend_values)[:5]]
                )
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text):
                findings["secrets"].append([rel, pattern])
        for index, pattern in enumerate(PRIVATE_PATTERNS):
            if re.search(pattern, text):
                findings["private_paths_or_refs"].append([rel, f"private pattern #{index}"])
    return {
        "files": len(entries) + 2,
        "index_sha256": sha256(EVIDENCE / INDEX),
        "manifest_sha256": sha256(EVIDENCE / "EVIDENCE_MANIFEST.json"),
        "total_bytes": sum(p.stat().st_size for p in EVIDENCE.rglob("*") if p.is_file()),
        "findings": findings,
    }


if __name__ == "__main__":
    result = build()
    print(json.dumps(result, indent=2))
    if any(result["findings"].values()):
        raise SystemExit("Drive evidence scan FAILED")
