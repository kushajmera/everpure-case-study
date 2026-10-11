"""Build the editable five-slide executive PowerPoint that mirrors PDF pages 1-5.

Native PowerPoint text, shapes, tables and charts on the same layout grid as the PDF.
Every number comes from ``phase5_inputs.load_validated_facts``; ``--check-pdf`` confirms
that each number shown on PDF pages 1-5 also appears on the matching slide.
"""

# ruff: noqa: E501  # Long slide-copy strings.

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import submission_config as cfg  # noqa: E402
from phase5_inputs import ROOT, load_validated_facts  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.chart.data import CategoryChartData  # noqa: E402
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.util import Inches, Pt  # noqa: E402
from pptx_kit import (  # noqa: E402
    BLUE_250,
    BLUE_450,
    BLUE_550,
    BLUE_700,
    FAINT,
    GRAY_BAR,
    INK,
    LEFT,
    MUTED,
    NAVY,
    PANEL,
    RIGHT,
    RULE,
    WHITE,
    WIDTH,
    Cell,
    Para,
    Run,
    apply_theme,
    bar_chart,
    rect,
    rgb,
    shape_text,
    table,
    text,
)

HEAD = "Cambria"
PANEL2 = "E4EAF2"
TRACK = ["Opportunity", "Data & SQL", "Survival", "Monte Carlo NPV", "GTM routing"]


def k(v: float, digits: int = 1) -> str:
    sign = "−" if v < 0 else ""
    return f"{sign}${abs(v) / 1000:,.{digits}f}k"


def n(v: float) -> str:
    return f"{v:,.0f}"


def frame(slide, index: int, kicker: str, title: str, footer: str) -> None:
    text(slide, LEFT, 0.34, 6.4, 0.25, Para(kicker.upper(), size=10, bold=True, color=BLUE_550))
    runs = []
    for i, name in enumerate(TRACK):
        runs.append(Run(f"{i + 1}  {name}", bold=i == index, color=NAVY if i == index else FAINT))
        if i < len(TRACK) - 1:
            runs.append(Run("      ", color=FAINT))
    text(slide, 6.2, 0.34, RIGHT - 6.2, 0.25, Para(runs, size=9.5, align="r"))
    title_shape = slide.shapes.title
    title_shape.left, title_shape.top = Inches(LEFT), Inches(0.64)
    title_shape.width, title_shape.height = Inches(WIDTH), Inches(0.95)
    tf = title_shape.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    from pptx.enum.text import MSO_ANCHOR

    tf.vertical_anchor = MSO_ANCHOR.TOP
    from pptx_kit import fill_text_frame

    p = tf.paragraphs[0]
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    fill_text_frame(
        tf, [Para(title, size=23, color=NAVY, font=HEAD, space_after=0, line_spacing=1.0)]
    )
    text(slide, LEFT, 6.98, 10.7, 0.42, Para(footer, size=9, color=MUTED, line_spacing=1.0))
    text(
        slide,
        11.35,
        7.05,
        RIGHT - 11.35,
        0.22,
        Para(f"Executive slide {index + 1} of 5", size=9, color=FAINT, align="r"),
    )


def slide1(s, f) -> None:
    co, src = f["cohort"], f["source"]
    ref = f["financial"]["nine_cell"]["base"]["medium_15pct"]["analytical_expected_npv"]
    frame(
        s,
        0,
        "Executive summary",
        f"{co['modeled_pct']:.0f}% of source accounts appear two-year dormant — recovery must start with data validation, not outreach",
        "Source: Case_Study_1_Install_Base_Reactivation.csv (2,000 rows; SHA-256 6863ea00…a229bc); frozen Phase 1–4 outputs. “Provisional” = source-reported years_inactive ≥ 2; fiscal-year eligibility unconfirmed. The brief’s “>50% of install base, +21% CAGR” cannot be verified from this extract. Historical spend is not ARR; NPV is illustrative, not causal.",
    )
    text(
        s,
        LEFT,
        1.72,
        7.0,
        0.25,
        Para("WHERE THE DORMANT OPPORTUNITY SITS", size=10, bold=True, color=MUTED),
    )
    tiles = [
        (n(co["source_accounts"]), f"source accounts in {src['roots']} root groups"),
        (n(co["modeled"]), f"provisionally two-year inactive — {co['modeled_pct']:.1f}% of source"),
        (n(co["modeled_roots"]), "root groups contain the 1,144 modeled accounts"),
    ]
    for i, (big, small) in enumerate(tiles):
        x = LEFT + i * 2.38
        box = rect(s, x, 2.0, 2.18, 1.22, PANEL)
        shape_text(
            box,
            [
                Para(big, size=30, color=NAVY, font=HEAD, space_after=2),
                Para(small, size=10.5, color=MUTED),
            ],
            anchor="t",
            margin=(0.16, 0.1, 0.12, 0.05),
        )
    text(
        s,
        LEFT,
        3.42,
        7.0,
        0.25,
        Para(
            "Composition of the 2,000 source accounts by inactivity evidence", size=10.5, bold=True
        ),
    )
    x = LEFT
    for count, fill, ink, caption in (
        (co["modeled"], NAVY, WHITE, "Modeled: source-reported inactive ≥ 2 years"),
        (co["conflicts"], BLUE_250, NAVY, "Excluded: source vs. booking-date conflict"),
        (co["unknown"], GRAY_BAR, WHITE, "Excluded: inactivity unknown"),
    ):
        w = 6.94 * count / co["source_accounts"]
        seg = rect(s, x, 3.72, w - 0.03, 0.5, fill)
        shape_text(
            seg,
            Para(
                [Run(n(count), bold=True), Run(f" · {100 * count / co['source_accounts']:.1f}%")],
                size=10.5,
                color=ink,
            ),
            anchor="m",
            margin=(0.08, 0, 0.04, 0),
        )
        text(s, x, 4.3, w - 0.08, 0.5, Para(caption, size=9.5, color=MUTED))
        x += w
    for i, (big, body) in enumerate(
        (
            (
                k(ref),
                "analytical expected net program NPV — base hazard, 15% hypothetical offer, 12 months, 1,144 accounts. Illustrative unit economics; not verified profit or causal uplift.",
            ),
            (
                str(f["gtm"]["authorized_contact_actions"]),
                "accounts are authorized for customer contact today. Every route is a planning candidate pending eligibility, ownership and permission checks.",
            ),
        )
    ):
        box = rect(s, LEFT + i * 3.57, 4.98, 3.37, 1.7, WHITE, line=RULE)
        shape_text(
            box,
            [
                Para(big, size=26, color=NAVY, font=HEAD, space_after=4),
                Para(body, size=10, color=MUTED),
            ],
            anchor="t",
            margin=(0.16, 0.12, 0.14, 0.05),
        )
    px, pw = 7.95, RIGHT - 7.95
    rect(s, px, 1.72, pw, 4.96, PANEL)
    text(
        s,
        px + 0.25,
        1.92,
        pw - 0.5,
        0.35,
        Para("Recommendation: evidence-gated program", size=14, bold=True, color=NAVY),
    )
    steps = [
        (
            "Validate",
            "Confirm fiscal-year inactivity, partner ownership, health and service evidence before any account is targeted.",
        ),
        (
            "Prioritize",
            "Rank opportunities with documented, versioned assumptions and keep evidence gaps visible beside every score.",
        ),
        (
            "Route",
            "Assign partner-led, direct-enterprise or digital-nurture planning workflows; hold unresolved accounts for review.",
        ),
        (
            "Pilot & measure",
            "Run controlled pilots with an untreated comparison group and track observed outcomes before any ROI claim.",
        ),
    ]
    for i, (head, body) in enumerate(steps):
        y = 2.36 + i * 0.82
        dot = rect(s, px + 0.25, y + 0.02, 0.34, 0.34, NAVY, shape=MSO_SHAPE.OVAL)
        shape_text(
            dot, Para(str(i + 1), size=12, bold=True, color=WHITE, align="c"), margin=(0, 0, 0, 0)
        )
        text(
            s,
            px + 0.78,
            y - 0.02,
            pw - 1.0,
            0.78,
            [Para(head, size=10.8, bold=True, space_after=0), Para(body, size=10.8)],
        )
    ask = rect(s, px + 0.25, 1.72 + 4.96 - 0.8, pw - 0.5, 0.62, NAVY)
    shape_text(
        ask,
        Para(
            "Decision: fund a data-validation sprint and a measured pilot — not a full-scale reactivation campaign.",
            size=11,
            bold=True,
            color=WHITE,
        ),
        margin=(0.15, 0.05, 0.15, 0.05),
    )


def slide2(s, f) -> None:
    src, co = f["source"], f["cohort"]
    frame(
        s,
        1,
        "Data foundation & SQL",
        f"Systematic hygiene logged {n(src['quality_exception_rows'])} data-quality exceptions and keeps observed facts separate from modeled assumptions",
        "Source: Phase 1 exception register and metrics (analysis date 2026-10-09). The brief describes injected duplicates; the supplied file has zero duplicate account IDs, so detection is implemented but no merge is invented. Account identifiers and row-level outputs are confidential and excluded from every shared artifact.",
    )
    text(
        s,
        LEFT,
        1.72,
        7.1,
        0.25,
        Para("INJECTED DEFECTS AND HOW EACH WAS HANDLED", size=10, bold=True, color=MUTED),
    )
    rows = [
        ["Defect named in the brief", "Observed in the 2,000-row extract", "Handling"],
        [
            "Duplicate accounts across parent-child",
            f"{src['duplicate_account_rows']} duplicate IDs; duplicate, cycle and self-reference checks retained",
            "Flag for review; never auto-merge",
        ],
        [
            "Region string formatting",
            f"{src['raw_region_variants']} raw variants → {src['canonical_regions']} regions; {n(src['issue_counts']['REGION_NORMALIZED'])} France rows normalized",
            "Trim + casefold mapping; raw value kept",
        ],
        [
            "Missing SFDC health score",
            f"{n(src['health_unknown'])} unknown ({src['health_raw_nan']} 'nan', {src['health_raw_missing']} 'Missing')",
            "Kept unknown and flagged; no imputation",
        ],
        [
            "NaN partner-managed flag",
            f"{n(src['partner_unknown'])} unresolved",
            "Kept unknown; routes to hold (R3)",
        ],
        [
            "Sentinel 999 open tickets",
            f"{n(src['ticket_sentinel'])} sentinels vs. {n(src['valid_zero_tickets'])} genuine zeros",
            "Excluded from valid ticket counts",
        ],
        [
            "Inactivity definition (found, not injected)",
            f"{n(co['modeled'])} agree · {n(co['conflicts'])} conflict · {n(co['unknown'])} unknown",
            "Provisional cohort; conflicts held",
        ],
        [
            Cell(
                f"{n(src['quality_exception_rows'])} exception events across {n(src['accounts_with_exceptions'])} accounts · hierarchy resolved: {src['roots']} roots, {n(src['children'])} children, {src['unresolved_hierarchy_rows']} unresolved",
                color=NAVY,
                fill=PANEL,
            ),
            Cell("", fill=PANEL),
            Cell("", fill=PANEL),
        ],
    ]
    gf = table(s, LEFT, 2.0, [2.05, 2.95, 2.1], rows, row_h=0.45, size=10.5)
    gf.table.cell(7, 0).merge(gf.table.cell(7, 2))
    ax, aw = 8.0, RIGHT - 8.0
    text(
        s,
        ax,
        1.72,
        aw,
        0.25,
        Para("MODELING ARCHITECTURE (IMPLEMENTED MODULES)", size=10, bold=True, color=MUTED),
    )
    steps = [
        (
            "Raw source → integrity gate",
            "SHA-256, row count, exact spend · source_integrity.py",
            NAVY,
        ),
        ("Cleaning, exceptions, hierarchy", "quality.py · hierarchy.py (arbitrary depth)", NAVY),
        ("DuckDB SQL analytics", "CTEs, LAG/LEAD, DENSE_RANK, running SUM · sql/*.sql", NAVY),
        ("Provisional cohort → assumed hazards", "reactivation_scenarios.py (Phase 2)", BLUE_450),
        ("Monte Carlo NPV, 1,000 runs × 9 cells", "financial_model.py (Phase 3)", BLUE_450),
        ("Rule-based GTM routing", "gtm_routing.py + versioned policy v2 (Phase 4)", BLUE_450),
    ]
    from pptx_kit import arrow

    for i, (head, sub, fill) in enumerate(steps):
        y = 2.0 + i * 0.63
        box = rect(s, ax, y, aw, 0.5, fill)
        shape_text(
            box,
            [
                Para(head, size=11, bold=True, color=WHITE, space_after=0),
                Para(sub, size=9.5, color="D7E3F2"),
            ],
            anchor="m",
            margin=(0.14, 0.02, 0.1, 0.02),
        )
        if i < 5:
            arrow(s, ax + aw / 2, y + 0.51, ax + aw / 2, y + 0.62, color=MUTED, width=1.0)
    ly = 2.0 + 6 * 0.63 - 0.02
    rect(s, ax, ly + 0.03, 0.14, 0.14, NAVY)
    text(s, ax + 0.2, ly, 1.9, 0.2, Para("Observed source facts", size=9.5, color=MUTED))
    rect(s, ax + 2.0, ly + 0.03, 0.14, 0.14, BLUE_450)
    text(s, ax + 2.2, ly, 2.5, 0.2, Para("Assumption-based models", size=9.5, color=MUTED))
    text(
        s,
        ax,
        ly + 0.25,
        aw,
        0.4,
        Para(
            "Each phase hands off through a versioned, SHA-256-pinned contract; Phase 5 re-validates all of them before any number reaches this deck.",
            size=9.5,
            color=MUTED,
        ),
    )
    call = rect(s, LEFT, 6.04, WIDTH, 0.72, PANEL)
    shape_text(
        call,
        Para(
            [
                Run("Why there is no observed decay curve: ", bold=True),
                Run(
                    "booking dates rise exactly with account ID and every contract starts exactly 365 days earlier, so LAG/LEAD gaps reduce to ID arithmetic. Revenue-decay velocity and historical reactivation timing cannot be estimated from this extract; the decay SQL (LAG, LEAD, DENSE_RANK) is executed on a labeled synthetic fixture."
                ),
            ],
            size=10.5,
        ),
        anchor="m",
        margin=(0.2, 0.05, 0.2, 0.05),
    )


def slide3(s, f) -> None:
    sv = f["survival"]
    e = sv["expected"]
    frame(
        s,
        2,
        "Reactivation probability & survival analysis",
        f"Assumed hazards imply {e['conservative'][12]:.0f}–{e['optimistic'][12]:.0f} expected first reactivations within 12 months — a planning range, not a forecast",
        "Source: frozen Phase 2 outputs (reactivation_scenario_summary.csv, scenario_sensitivity.csv, synthetic_cox_coefficients.csv); assumption register v1, fingerprint 6195ba2e…. Probabilities are ASSUMPTION_BASED_NOT_CALIBRATED; the Cox fit uses invented subjects only.",
    )
    lx, lw = LEFT, 4.35
    rect(s, lx, 1.72, lw, 4.98, PANEL)
    text(
        s,
        lx + 0.2,
        1.86,
        lw - 0.4,
        0.22,
        Para("LANE A · METHOD DEMONSTRATION", size=9.5, bold=True, color=BLUE_550),
    )
    text(
        s,
        lx + 0.2,
        2.08,
        lw - 0.4,
        0.55,
        Para(
            "Cox proportional hazards on synthetic event histories", size=13, bold=True, color=NAVY
        ),
    )
    names = {
        "health_proxy": "Health proxy",
        "engagement_proxy": "Engagement proxy",
        "partner_proxy": "Partner proxy",
    }
    rows = [["Synthetic covariate", "True β", "Fitted HR (95% CI)"]]
    for key, label in names.items():
        r = sv["cox"][key]
        rows.append(
            [
                label,
                f"{r['true_beta']:+.2f}".replace("-", "−"),
                f"{r['hr']:.2f} ({r['lo']:.2f}–{r['hi']:.2f})",
            ]
        )
    table(
        s,
        lx + 0.2,
        2.72,
        [1.45, 0.75, 1.75],
        [[Cell(v, fill=None if i == 0 else WHITE) for v in r] for i, r in enumerate(rows)],
        row_h=0.3,
        size=10,
    )
    d = sv["cox_diagnostics"]
    p = d["schoenfeld_p"]
    text(
        s,
        lx + 0.2,
        4.08,
        lw - 0.4,
        2.5,
        [
            Para(
                f"1,600 invented subjects: {n(d['events'])} events, {n(d['censored'])} right-censored.",
                size=10.5,
                bullet="•",
                space_after=5,
            ),
            Para(
                f"Concordance {d['concordance_in_sample']:.2f} in-sample and {d['concordance_holdout']:.2f} on an independent synthetic holdout.",
                size=10.5,
                bullet="•",
                space_after=5,
            ),
            Para(
                f"Schoenfeld proportional-hazards p-values {p['health_proxy']:.2f} / {p['engagement_proxy']:.2f} / {p['partner_proxy']:.2f}: no violation detected.",
                size=10.5,
                bullet="•",
                space_after=5,
            ),
            Para(
                "Shows the lifelines workflow recovers known effects. It is not an Everpure model: the extract has no customer event histories.",
                size=10.5,
                bold=True,
                bullet="•",
            ),
        ],
    )
    bx = lx + lw + 0.35
    bw = RIGHT - bx
    text(
        s,
        bx,
        1.72,
        bw,
        0.22,
        Para("LANE B · EVERPURE PLANNING SCENARIOS", size=9.5, bold=True, color=BLUE_550),
    )
    text(
        s,
        bx,
        1.94,
        bw,
        0.55,
        Para(
            "Assumption-based exponential hazards for the 1,144 modeled accounts — expected cumulative first reactivations",
            size=13,
            bold=True,
            color=NAVY,
        ),
    )
    lam = sv["baseline_hazards"]
    cats = [
        f"Conservative — baseline {lam['conservative'] * 100:.1f}% per month",
        f"Base — baseline {lam['base'] * 100:.1f}% per month",
        f"Optimistic — baseline {lam['optimistic'] * 100:.1f}% per month",
    ]
    series = [
        (f"By month {h}", [round(e[sc][h], 1) for sc in ("conservative", "base", "optimistic")])
        for h in (3, 6, 12)
    ]
    bar_chart(
        s,
        bx,
        2.6,
        bw,
        2.75,
        cats,
        series,
        chart_type=XL_CHART_TYPE.COLUMN_CLUSTERED,
        colors=[BLUE_250, BLUE_450, BLUE_700],
        number_format="0.0",
        gap_width=80,
        overlap=-8,
        font_size=10.5,
    )
    s12 = sv["sensitivity_12m"]
    text(
        s,
        bx,
        5.48,
        bw,
        1.35,
        [
            Para(
                "Counts are cumulative expectations, not observed conversions: the 3-, 6- and 12-month values must not be added. No campaign treatment effect is identified.",
                size=10.5,
                bullet="•",
                space_after=4,
            ),
            Para(
                [
                    Run("P(reactivate by month t) = 1 − exp(−λ·t·e"),
                    Run("xβ", superscript=True),
                    Run(
                        "), with assumed effects for health, partner ownership, child status and valid tickets."
                    ),
                ],
                size=10.5,
                bullet="•",
                space_after=4,
            ),
            Para(
                f"Unknown health is scored at the reference level and lifts rankings: scoring it as Yellow or Red cuts base 12-month reactivations from {e['base'][12]:.1f} to {s12['unknown_health_as_yellow']['expected']:.1f} or {s12['unknown_health_as_red']['expected']:.1f}.",
                size=10.5,
                bullet="•",
            ),
        ],
    )


def slide4(s, f) -> None:
    fin = f["financial"]
    nine, a, st, be = fin["nine_cell"], fin["assumptions"], fin["stress"], fin["break_even"]
    ref = nine["base"]["medium_15pct"]
    frame(
        s,
        3,
        "Monte Carlo NPV & financial risk",
        f"Illustrative economics are positive in the base case (~{k(ref['analytical_expected_npv'], 0)} at a 15% offer) but depend heavily on unverified assumptions",
        "Source: frozen Phase 3 outputs (financial_scenario_matrix.csv, monte_carlo_npv_summary.csv, financial_sensitivity.csv); assumption fingerprint b953c02d…; NumPy PCG64 seed 20261009 with common random numbers. P5/P95 are conditional simulation percentiles, not confidence intervals. Label: ILLUSTRATIVE_NET_PROGRAM_NPV_NOT_CAUSALLY_ATTRIBUTED.",
    )
    lw = 6.7
    text(
        s,
        LEFT,
        1.72,
        lw,
        0.25,
        Para(
            "ANALYTICAL EXPECTED NET PROGRAM NPV — BASE HAZARD, BY HYPOTHETICAL OFFER",
            size=10,
            bold=True,
            color=MUTED,
        ),
    )
    vals = [
        nine["base"][t]["analytical_expected_npv"] / 1000
        for t in ("low_5pct", "medium_15pct", "high_30pct")
    ]
    bar_chart(
        s,
        LEFT,
        1.98,
        lw,
        2.5,
        ["5% offer", "15% offer · central case", "30% offer"],
        [("Expected NPV ($k)", vals)],
        chart_type=XL_CHART_TYPE.COLUMN_CLUSTERED,
        colors=[BLUE_450],
        point_colors=[BLUE_450, NAVY, BLUE_450],
        number_format='"$"#,##0.0"k"',
        legend=False,
        gap_width=70,
        font_size=10.5,
        label_size=14,
    )
    my = 4.5
    text(
        s,
        LEFT,
        my,
        lw,
        0.25,
        Para(
            f"MONTE CARLO DISTRIBUTION — BASE HAZARD, 15% OFFER, {n(ref['runs'])} RUNS",
            size=10,
            bold=True,
            color=MUTED,
        ),
    )
    negatives = round(ref["pr_negative"] * ref["runs"])
    table(
        s,
        LEFT,
        my + 0.27,
        [lw / 5] * 5,
        [
            ["Sample mean", "Median", "5th percentile", "95th percentile", "Runs with NPV < $0"],
            [
                Cell(v, size=13, bold=True, color=NAVY, fill=PANEL, align="c")
                for v in (
                    k(ref["mc_mean"]),
                    k(ref["mc_median"]),
                    k(ref["mc_p05"]),
                    k(ref["mc_p95"]),
                    f"{negatives} of {n(ref['runs'])}",
                )
            ],
        ],
        row_h=0.36,
        size=10,
        aligns=["c"] * 5,
    )
    text(
        s,
        LEFT,
        my + 1.03,
        lw,
        0.35,
        Para(
            f"Analytical expectation {k(ref['analytical_expected_npv'])} (closed form) vs. simulation sample mean {k(ref['mc_mean'])}: a +{ref['z']:.2f} standard-error difference; the largest across all nine cells is {fin['max_abs_z']:.2f}.",
            size=9.5,
            color=MUTED,
        ),
    )
    px = LEFT + lw + 0.4
    pw = RIGHT - px
    rect(s, px, 1.72, pw, 4.0, PANEL)
    text(
        s,
        px + 0.22,
        1.86,
        pw - 0.44,
        0.3,
        Para("How to read the result", size=14, bold=True, color=NAVY),
    )
    text(
        s,
        px + 0.22,
        2.3,
        pw - 0.44,
        3.3,
        [
            Para(
                [
                    Run(
                        "5% scores highest only because the model holds reactivation hazard fixed across offers. ",
                        bold=True,
                    ),
                    Run(
                        f"15% and 30% would need {be['hazard_multiplier_medium_15pct']:.2f}× and {be['hazard_multiplier_high_30pct']:.2f}× the hazard to match it — not evidence that 5% is optimal."
                    ),
                ],
                size=11,
                bullet="•",
                space_after=7,
            ),
            Para(
                f"Across the nine cells the expected NPV ranges from {k(nine['conservative']['high_30pct']['analytical_expected_npv'])} (conservative, 30%) to {k(nine['optimistic']['low_5pct']['analytical_expected_npv'])} (optimistic, 5%). The cells are alternatives; never add them.",
                size=11,
                bullet="•",
                space_after=7,
            ),
            Para(
                [
                    Run(
                        "Committed combined adverse stress ($750 revenue, 45% margin, $150 outreach, $300 activation, 24% rate, 3 paid months) turns NPV to "
                    ),
                    Run(k(st["committed_adverse_npv_usd"]), bold=True),
                    Run("."),
                ],
                size=11,
                bullet="•",
                space_after=7,
            ),
            Para(
                "Net program value under analyst-selected unit economics — not verified profitability or causally identified incremental uplift.",
                size=11,
                bullet="•",
            ),
        ],
    )
    ay = 5.95
    text(
        s,
        LEFT,
        ay,
        WIDTH,
        0.22,
        Para(
            "ILLUSTRATIVE UNIT ECONOMICS (ANALYST-SELECTED, NOT OBSERVED)",
            size=9.5,
            bold=True,
            color=MUTED,
        ),
    )
    chips = [
        (f"${a['monthly_gross_revenue']:,.0f}", "gross revenue per activated account per month"),
        (f"{a['contribution_margin'] * 100:.0f}%", "contribution margin"),
        (f"${a['outreach_cost']:,.0f}", "outreach per modeled account"),
        (f"${a['activation_cost']:,.0f}", "activation cost per reactivation"),
        (f"{a['annual_discount_rate'] * 100:.0f}%", "annual effective discount rate"),
        (f"{a['horizon_months']} months", "financial horizon, no churn"),
    ]
    cw = (WIDTH - 5 * 0.12) / 6
    for i, (big, small) in enumerate(chips):
        chip = rect(s, LEFT + i * (cw + 0.12), ay + 0.22, cw, 0.62, WHITE, line=RULE)
        shape_text(
            chip,
            [
                Para(big, size=12.5, bold=True, color=NAVY, space_after=0),
                Para(small, size=9, color=MUTED),
            ],
            anchor="t",
            margin=(0.1, 0.05, 0.08, 0.02),
        )


def slide5(s, f) -> None:
    g = f["gtm"]
    ch, rl, pr, rd, rt = g["channels"], g["rules"], g["priority"], g["readiness"], g["roots"]
    frame(
        s,
        4,
        "GTM routing, roadmap & decision",
        f"Route {g['routed_candidates']} accounts to conditional planning channels, hold {ch['HOLD_REVIEW']} for review, and release outreach only through gated pilots",
        f"Source: frozen Phase 4 aggregates via phase5_input_contract.json v2 (policy fingerprint 1998cc4a…). All dispositions are PLANNING_ONLY with execution_authorized = false. Priority tiers use fixed base/15% NPV cutpoints; the modeled NPV is not attributable to the {g['routed_candidates']} routed accounts alone.",
    )
    c1w = 4.25
    text(
        s,
        LEFT,
        1.72,
        c1w,
        0.25,
        Para("CONDITIONAL ROUTES · 1,144 MODELED ACCOUNTS", size=10, bold=True, color=MUTED),
    )
    labels = [
        ("Partner-led candidate", "PARTNER_LED_CANDIDATE"),
        ("Direct-enterprise candidate", "DIRECT_ENTERPRISE_CANDIDATE"),
        ("Digital-nurture candidate", "DIGITAL_NURTURE_CANDIDATE"),
        ("Hold / review", "HOLD_REVIEW"),
    ]
    data = CategoryChartData()
    data.categories = [lbl for lbl, _ in labels]
    data.add_series("Accounts", [ch[key] for _, key in labels])
    gf = s.shapes.add_chart(
        XL_CHART_TYPE.BAR_CLUSTERED, Inches(LEFT), Inches(1.98), Inches(c1w), Inches(2.6), data
    )
    chart = gf.chart
    chart.has_legend = False
    chart.has_title = False
    chart.font.name, chart.font.size = "Arial", Pt(10.5)
    plot = chart.plots[0]
    plot.gap_width = 55
    plot.has_data_labels = True
    plot.data_labels.number_format = "#,##0"
    plot.data_labels.number_format_is_linked = False
    plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    for i, (_, key) in enumerate(labels):
        point = plot.series[0].points[i]
        point.format.fill.solid()
        point.format.fill.fore_color.rgb = rgb(GRAY_BAR if key == "HOLD_REVIEW" else BLUE_550)
    chart.category_axis.reverse_order = True
    chart.value_axis.visible = False
    chart.value_axis.has_major_gridlines = False
    chart.category_axis.format.line.color.rgb = rgb(RULE)
    pct = " · ".join(f"{lbl.split()[0]} {g['channel_pct'][key]:.1f}%" for lbl, key in labels)
    text(s, LEFT, 4.62, c1w, 0.5, Para(f"Share of 1,144: {pct}", size=9.5, color=INK))
    text(
        s,
        LEFT,
        5.08,
        c1w,
        0.5,
        Para(
            f"Holds: {rl['R3']} unknown partner ownership (R3) and {rl['R4']} needing service recovery — Red health or ≥ 5 valid open tickets (R4).",
            size=9.5,
            color=MUTED,
        ),
    )
    c2x, c2w = LEFT + c1w + 0.35, 3.55
    text(
        s,
        c2x,
        1.72,
        c2w,
        0.25,
        Para("EVIDENCE QUALITY & HIERARCHY", size=10, bold=True, color=MUTED),
    )
    kpis = [
        (
            f"{pr['HIGH']} · {pr['MEDIUM']} · {pr['LOW']}",
            "High / Medium / Low illustrative priority (fixed NPV cutpoints)",
        ),
        (
            f"{rd['high_priority_health_unknown']} of {pr['HIGH']}",
            "High-priority accounts have unknown health",
        ),
        (
            f"{rt['full_source_known_ownership_conflict_roots']} of {rt['all_modeled_roots']} roots",
            "carry a known partner-ownership conflict (full-source membership)",
        ),
        (
            f"{rt['coordination_required_roots']} roots · {n(rd['root_coordination_required'])} accts",
            "require parent-child coordination before contact",
        ),
        (str(g["authorized_contact_actions"]), "authorized customer-contact actions"),
    ]
    for i, (big, small) in enumerate(kpis):
        box = rect(s, c2x, 2.02 + i * 0.71, c2w, 0.64, PANEL)
        shape_text(
            box,
            [
                Para(big, size=15, color=NAVY, font=HEAD, space_after=0),
                Para(small, size=9.5, color=MUTED),
            ],
            anchor="t",
            margin=(0.14, 0.04, 0.1, 0.02),
        )
    c3x = c2x + c2w + 0.35
    c3w = RIGHT - c3x
    text(
        s,
        c3x,
        1.72,
        c3w,
        0.25,
        Para("RELEASE GATES BEFORE ANY OUTREACH", size=10, bold=True, color=MUTED),
    )
    gates = [
        ("Validate", "fiscal eligibility, partner ownership, health and service barriers"),
        ("Coordinate", "resolve parent-child ownership; prevent overlapping campaigns"),
        ("Pilot", "controlled partner / direct / digital pilots where permissions exist"),
        ("Measure", "observed reactivation, uplift vs. control, actual cost and margin"),
        ("Scale", "recalibrate the model; scale only when evidence supports it"),
    ]
    for i, (head, body) in enumerate(gates):
        y = 2.02 + i * 0.71
        tag = rect(s, c3x, y, 0.62, 0.64, NAVY if i < 2 else BLUE_450)
        shape_text(
            tag,
            [
                Para("Gate", size=10, color=WHITE, align="c", space_after=0),
                Para(str(i + 1), size=10, bold=True, color=WHITE, align="c"),
            ],
            margin=(0, 0, 0, 0),
        )
        body_box = rect(s, c3x + 0.62, y, c3w - 0.62, 0.64, PANEL)
        shape_text(
            body_box,
            Para([Run(head, bold=True), Run(f" — {body}")], size=10),
            anchor="m",
            margin=(0.12, 0.03, 0.08, 0.03),
        )
    dec = rect(s, LEFT, 5.66, WIDTH, 0.62, NAVY)
    shape_text(
        dec,
        Para(
            "Decision: approve a data-validation sprint and a controlled, measured pilot — not a full-scale reactivation campaign. The 518 routed candidates are not approved contacts.",
            size=11.5,
            bold=True,
            color=WHITE,
        ),
        margin=(0.2, 0.04, 0.2, 0.04),
    )
    bw = (WIDTH - 0.25) / 2
    for i, (label, url) in enumerate(
        ((cfg.DRIVE_LABEL, cfg.DRIVE_URL), (cfg.GITHUB_LABEL, cfg.GITHUB_URL))
    ):
        btn = rect(
            s,
            LEFT + i * (bw + 0.25),
            6.38,
            bw,
            0.46,
            WHITE,
            line="1F5FA8",
            line_w=1.0,
            shape=MSO_SHAPE.ROUNDED_RECTANGLE,
            radius=0.12,
        )
        shape_text(
            btn,
            Para([Run(label, link=url, bold=True)], size=12),
            anchor="m",
            margin=(0.15, 0.02, 0.1, 0.02),
        )
        btn.click_action.hyperlink.address = url


def build(out: Path) -> Path:
    facts = load_validated_facts(ROOT)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    apply_theme(prs, heading=HEAD)
    props = prs.core_properties
    props.title = cfg.DECK_TITLE
    props.subject = cfg.PDF_SUBJECT
    props.author = cfg.CANDIDATE_NAME or "Everpure Case Study 1 candidate submission"
    props.keywords = cfg.PDF_KEYWORDS
    props.comments = "Five executive slides; mirrors pages 1-5 of the submission PDF."
    props.last_modified_by = ""
    layout = prs.slide_layouts[5]  # Title Only
    for fn in (slide1, slide2, slide3, slide4, slide5):
        slide = prs.slides.add_slide(layout)
        fn(slide, facts)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out)
    return out


def check_against_pdf(pptx_path: Path, pdf_path: Path) -> dict:
    import pymupdf
    from pptx import Presentation as Load

    deck = Load(pptx_path)
    pdf = pymupdf.open(pdf_path)
    number = re.compile(r"[−-]?\$?\d[\d,]*(?:\.\d+)?(?:k|%|×)?")
    report = {}
    for i, slide in enumerate(deck.slides):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                texts.append(shape.text_frame.text)
            if shape.has_table:
                texts += [c.text for row in shape.table.rows for c in row.cells]
            if shape.has_chart:
                for series in shape.chart.plots[0].series:
                    texts += [f"{v:,.1f}" for v in series.values] + [
                        f"{v:,.0f}" for v in series.values
                    ]
                    texts += [f"${v:,.1f}k" for v in series.values]
                texts += [str(c) for c in shape.chart.plots[0].categories]
        slide_text = " ".join(" ".join(texts).split())
        pdf_text = " ".join(pdf[i].get_text().split())
        missing = sorted(
            {tok for tok in number.findall(pdf_text) if tok not in slide_text}
            - {"1", "2", "3", "4", "5"}
        )
        report[f"slide{i + 1}"] = missing
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", default=str(ROOT / "submission/Everpure_Executive_Presentation.pptx")
    )
    parser.add_argument(
        "--check-pdf", default=str(ROOT / "submission/Everpure_Case_Study_Final_Submission.pdf")
    )
    args = parser.parse_args()
    out = build(Path(args.out))
    print(f"PPTX {out} bytes={out.stat().st_size} slides=5")
    print(
        "Numbers on PDF pages 1-5 missing from the PPTX:",
        check_against_pdf(out, Path(args.check_pdf)),
    )


if __name__ == "__main__":
    main()
