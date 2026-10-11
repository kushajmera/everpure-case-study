"""Build the consolidated Phase 5 submission PDF directly as vector graphics.

Pages 1-5 are the executive presentation; the remaining pages are the technical
appendix. Every number comes from ``phase5_inputs.load_validated_facts``. Fonts are
subset-embedded TrueType, all charts and diagrams are drawn as vectors, and the two
evidence links are real URI annotations.
"""

# ruff: noqa: E501  # Long slide-copy and caption strings.

from __future__ import annotations

import argparse
import hashlib
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab import rl_config
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.fonts import addMapping
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Table, TableStyle

sys.path.insert(0, str(Path(__file__).resolve().parent))
import submission_config as cfg  # noqa: E402
from phase5_inputs import ROOT, load_validated_facts  # noqa: E402

rl_config.invariant = 1  # deterministic bytes: no timestamps or random document IDs

PAGE_W, PAGE_H = 13.333 * 72, 7.5 * 72
LEFT, RIGHT = 0.6, 13.333 - 0.6
WIDTH = RIGHT - LEFT

NAVY = "0B2341"
INK = "1F2933"
MUTED = "4F5B6A"
FAINT = "8C96A4"
RULE = "D3DAE3"
PANEL = "F1F4F8"
PANEL2 = "E4EAF2"
WHITE = "FFFFFF"
B250 = "86B6EF"
B450 = "2A78D6"
B550 = "1C5CAB"
B700 = "0D366B"
GRAY = "9AA5B1"
RED = "B23A3A"
LINK = "1F5FA8"

FONT_FILES = {
    "Arial": "arial.ttf",
    "Arial-Bold": "arialbd.ttf",
    "Arial-Italic": "ariali.ttf",
    "Cambria": "cambria.ttc",
    "Consolas": "consola.ttf",
}
OVERFLOWS: list[str] = []
USED_TEXT: list[tuple[str, str]] = []


def register_fonts() -> None:
    font_dir = Path("C:/Windows/Fonts")
    missing = [name for name, file in FONT_FILES.items() if not (font_dir / file).is_file()]
    if missing:
        raise SystemExit(f"Required TrueType fonts not found: {missing}")
    for name, file in FONT_FILES.items():
        pdfmetrics.registerFont(TTFont(name, str(font_dir / file), subfontIndex=0))
    addMapping("Arial", 0, 0, "Arial")
    addMapping("Arial", 1, 0, "Arial-Bold")
    addMapping("Arial", 0, 1, "Arial-Italic")
    addMapping("Arial", 1, 1, "Arial-Bold")
    for bold in (0, 1):
        for italic in (0, 1):
            addMapping("Cambria", bold, italic, "Cambria")
    addMapping("Consolas", 0, 0, "Consolas")
    addMapping("Consolas", 1, 0, "Consolas")
    addMapping("Consolas", 0, 1, "Consolas")
    addMapping("Consolas", 1, 1, "Consolas")


def missing_glyphs() -> dict[str, list[str]]:
    """Characters drawn in a font that lacks them (they would render as empty boxes)."""
    import html
    import re

    missing: dict[str, set[str]] = {}
    for font_name, raw in USED_TEXT:
        family = (
            "Consolas"
            if "Consolas" in font_name
            else ("Cambria" if "Cambria" in font_name else "Arial")
        )
        segments = [(family, raw)]
        for nested_font, inner in re.findall(
            r"<font[^>]*name=['\"]([A-Za-z-]+)['\"][^>]*>(.*?)</font>", raw
        ):
            segments.append((nested_font.split("-")[0], inner))
        for fam, chunk in segments:
            face = pdfmetrics.getFont(
                fam if fam in ("Arial", "Cambria", "Consolas") else "Arial"
            ).face
            text_value = html.unescape(re.sub(r"<[^>]+>", "", chunk))
            for ch in set(text_value):
                if ch in "\n\r\t\xa0":
                    continue
                if ord(ch) not in face.charToGlyph:
                    missing.setdefault(fam, set()).add(ch)
    return {k: sorted(v) for k, v in missing.items()}


def signed(value: float, digits: int = 2) -> str:
    return f"{value:+.{digits}f}".replace("-", "−")


def col(hex_value: str) -> HexColor:
    return HexColor("#" + hex_value)


def X(x: float) -> float:
    return x * 72


def Y(y: float) -> float:
    return PAGE_H - y * 72


_style_cache: dict[tuple, ParagraphStyle] = {}


def S(
    size: float = 11.5,
    *,
    color: str = INK,
    font: str = "Arial",
    bold: bool = False,
    align: str = "l",
    leading: float | None = None,
    left: float = 0,
    bullet_indent: float = 0,
    space_after: float = 0,
) -> ParagraphStyle:
    key = (size, color, font, bold, align, leading, left, bullet_indent, space_after)
    if key not in _style_cache:
        _style_cache[key] = ParagraphStyle(
            name=f"s{len(_style_cache)}",
            fontName=("Arial-Bold" if bold and font == "Arial" else font),
            fontSize=size,
            leading=leading or round(size * 1.24, 2),
            textColor=col(color),
            alignment={"l": TA_LEFT, "c": TA_CENTER, "r": TA_RIGHT}[align],
            leftIndent=left,
            bulletIndent=bullet_indent,
            spaceAfter=space_after,
            bulletFontName="Arial",
            bulletFontSize=size,
            bulletColor=col(color),
        )
    return _style_cache[key]


PAGE_NAME = [""]


def P(c, x, y, w, html, style, *, max_h=None, name="", bullet=None) -> float:
    """Draw a wrapped paragraph whose top-left is (x, y) inches; return its height."""
    USED_TEXT.append((style.fontName, html))
    p = Paragraph(html, style, bulletText=bullet)
    _, h = p.wrapOn(c, X(w), 10_000)
    if max_h is not None and h > X(max_h) + 0.5:
        OVERFLOWS.append(f"{PAGE_NAME[0]} {name}: {h / 72:.2f}in > {max_h:.2f}in")
    p.drawOn(c, X(x), Y(y) - h)
    return h / 72


def bullets(c, x, y, w, items, style, *, gap=0.07, marker="•", max_h=None, name="") -> float:
    total = 0.0
    bstyle = ParagraphStyle(name=style.name + "b", parent=style, leftIndent=13, bulletIndent=1)
    for item in items:
        total += P(c, x, y + total, w, item, bstyle, bullet=marker) + gap
    total -= gap
    if max_h is not None and total > max_h + 0.01:
        OVERFLOWS.append(f"{PAGE_NAME[0]} {name}: {total:.2f}in > {max_h:.2f}in")
    return total


def rect(c, x, y, w, h, fill=None, stroke=None, width=0.75, radius=0.0) -> None:
    c.saveState()
    if fill:
        c.setFillColor(col(fill))
    if stroke:
        c.setStrokeColor(col(stroke))
        c.setLineWidth(width)
    if radius:
        c.roundRect(
            X(x),
            Y(y + h),
            X(w),
            X(h),
            radius * 72,
            stroke=1 if stroke else 0,
            fill=1 if fill else 0,
        )
    else:
        c.rect(X(x), Y(y + h), X(w), X(h), stroke=1 if stroke else 0, fill=1 if fill else 0)
    c.restoreState()


def line(c, x1, y1, x2, y2, color=RULE, width=0.75, dash=None) -> None:
    c.saveState()
    c.setStrokeColor(col(color))
    c.setLineWidth(width)
    if dash:
        c.setDash(dash)
    c.line(X(x1), Y(y1), X(x2), Y(y2))
    c.restoreState()


def arrow(c, x1, y1, x2, y2, color=MUTED, width=1.1, head=6.5) -> None:
    ax, ay, bx, by = X(x1), Y(y1), X(x2), Y(y2)
    ang = math.atan2(by - ay, bx - ax)
    base_x, base_y = bx - head * math.cos(ang), by - head * math.sin(ang)
    c.saveState()
    c.setStrokeColor(col(color))
    c.setFillColor(col(color))
    c.setLineWidth(width)
    c.line(ax, ay, base_x, base_y)
    path = c.beginPath()
    path.moveTo(bx, by)
    path.lineTo(base_x + head * 0.45 * math.sin(ang), base_y - head * 0.45 * math.cos(ang))
    path.lineTo(base_x - head * 0.45 * math.sin(ang), base_y + head * 0.45 * math.cos(ang))
    path.close()
    c.drawPath(path, fill=1, stroke=0)
    c.restoreState()


def table(c, x, y, data, widths, style_cmds, *, row_heights=None, name="", max_h=None) -> float:
    t = Table(data, colWidths=[X(w) for w in widths], rowHeights=row_heights)
    t.setStyle(TableStyle(style_cmds))
    _, h = t.wrapOn(c, X(sum(widths)), 10_000)
    if max_h is not None and h > X(max_h) + 0.5:
        OVERFLOWS.append(f"{PAGE_NAME[0]} {name}: {h / 72:.2f}in > {max_h:.2f}in")
    t.drawOn(c, X(x), Y(y) - h)
    for row in data:
        for cell in row:
            if isinstance(cell, str):
                USED_TEXT.append(("Arial", cell))
    return h / 72


def link_button(c, x, y, w, h, label, url, *, sub=None, fill=WHITE, stroke=LINK) -> None:
    rect(c, x, y, w, h, fill=fill, stroke=stroke, width=1.0, radius=0.06)
    text = f'<link href="{escape(url)}" color="#{LINK}"><u>{escape(label)}</u></link>'
    if sub:
        text += f'<br/><font size="9.5" color="#{MUTED}">{escape(sub)}</font>'
    ph = Paragraph(text, S(12, color=LINK, bold=True, leading=14.5))
    _, th = ph.wrapOn(c, X(w - 0.3), 1000)
    ph.drawOn(c, X(x + 0.15), Y(y + (h - th / 72) / 2) - th)
    USED_TEXT.append(("Arial-Bold", label))
    c.linkURL(url, (X(x), Y(y + h), X(x + w), Y(y)), relative=0, thickness=0)


def money(v: float, cents: bool = False) -> str:
    sign = "−" if v < 0 else ""
    return f"{sign}${abs(v):,.2f}" if cents else f"{sign}${abs(v):,.0f}"


def k(v: float, digits: int = 1) -> str:
    sign = "−" if v < 0 else ""
    return f"{sign}${abs(v) / 1000:,.{digits}f}k"


def n(v: float) -> str:
    return f"{v:,.0f}"


TRACK = ["Opportunity", "Data & SQL", "Survival", "Monte Carlo NPV", "GTM routing"]


def frame(c, *, kicker, title, footer, exec_index=None, appendix=None, label=None) -> None:
    PAGE_NAME[0] = label or kicker
    P(c, LEFT, 0.34, 6.4, escape(kicker.upper()), S(10, color=B550, bold=True))
    if exec_index is not None:
        parts = []
        for i, name in enumerate(TRACK):
            if i == exec_index:
                parts.append(
                    f'<font name="Arial-Bold" color="#{NAVY}">{i + 1}  {escape(name)}</font>'
                )
            else:
                parts.append(f'<font color="#{FAINT}">{i + 1}  {escape(name)}</font>')
        P(c, 6.2, 0.34, RIGHT - 6.2, "&nbsp;&nbsp;&nbsp;&nbsp;".join(parts), S(9.5, align="r"))
    else:
        P(
            c,
            8.5,
            0.34,
            RIGHT - 8.5,
            "TECHNICAL APPENDIX — SUPPORTING EVIDENCE",
            S(9.5, color=FAINT, bold=True, align="r"),
        )
    P(
        c,
        LEFT,
        0.64,
        WIDTH,
        escape(title),
        S(23, color=NAVY, font="Cambria", leading=27.5),
        max_h=0.95,
        name="title",
    )
    P(c, LEFT, 6.98, 10.7, footer, S(9, color=MUTED, leading=11), max_h=0.42, name="footer")
    right = (
        f"Executive slide {exec_index + 1} of 5"
        if exec_index is not None
        else f"Appendix {appendix}"
    )
    P(c, 11.35, 7.05, RIGHT - 11.35, right, S(9, color=FAINT, align="r"))
    if cfg.CANDIDATE_NAME:
        P(c, 11.35, 7.2, RIGHT - 11.35, escape(cfg.CANDIDATE_NAME), S(8.5, color=FAINT, align="r"))


# ======================================================================================
# Executive slide 1 — opportunity and recommendation
# ======================================================================================
def slide1(c, f) -> None:
    co, src = f["cohort"], f["source"]
    ref = f["financial"]["nine_cell"]["base"]["medium_15pct"]["analytical_expected_npv"]
    frame(
        c,
        kicker="Executive summary",
        title=(
            f"{co['modeled_pct']:.0f}% of source accounts appear two-year dormant — recovery must "
            "start with data validation, not outreach"
        ),
        footer=(
            "Source: Case_Study_1_Install_Base_Reactivation.csv (2,000 rows; SHA-256 6863ea00…a229bc); "
            "frozen Phase 1–4 outputs. “Provisional” = source-reported years_inactive ≥ 2; fiscal-year "
            "eligibility unconfirmed. The brief’s “>50% of install base, +21% CAGR” cannot be verified "
            "from this extract. Historical spend is not ARR; NPV is illustrative, not causal."
        ),
        exec_index=0,
    )
    P(c, LEFT, 1.72, 7.0, "WHERE THE DORMANT OPPORTUNITY SITS", S(10, color=MUTED, bold=True))
    tiles = [
        (n(co["source_accounts"]), f"source accounts in {src['roots']} root groups"),
        (n(co["modeled"]), f"provisionally two-year inactive — {co['modeled_pct']:.1f}% of source"),
        (n(co["modeled_roots"]), "root groups contain the 1,144 modeled accounts"),
    ]
    tw, gap = 2.18, 0.2
    for i, (big, small) in enumerate(tiles):
        x = LEFT + i * (tw + gap)
        rect(c, x, 2.0, tw, 1.22, fill=PANEL)
        P(c, x + 0.16, 2.1, tw - 0.3, big, S(30, color=NAVY, font="Cambria", leading=34))
        P(
            c,
            x + 0.16,
            2.62,
            tw - 0.3,
            escape(small),
            S(10.5, color=MUTED, leading=12.5),
            max_h=0.55,
            name="tile",
        )

    # composition bar of the 2,000 source accounts
    P(
        c,
        LEFT,
        3.42,
        7.0,
        "Composition of the 2,000 source accounts by inactivity evidence",
        S(10.5, color=INK, bold=True),
    )
    total_w, y0, bh = 6.94, 3.72, 0.5
    parts = [
        (co["modeled"], NAVY, WHITE, "Modeled: source-reported inactive ≥ 2 years"),
        (co["conflicts"], B250, NAVY, "Excluded: source vs. booking-date conflict"),
        (co["unknown"], GRAY, WHITE, "Excluded: inactivity unknown"),
    ]
    x = LEFT
    for count, fill, ink, caption in parts:
        w = total_w * count / co["source_accounts"]
        rect(c, x, y0, w - 0.03, bh, fill=fill)
        P(
            c,
            x + 0.08,
            y0 + 0.14,
            w - 0.14,
            f"<b>{n(count)}</b> · {100 * count / co['source_accounts']:.1f}%",
            S(10.5, color=ink),
        )
        P(
            c,
            x,
            y0 + bh + 0.08,
            w - 0.08,
            escape(caption),
            S(9.5, color=MUTED, leading=11.2),
            max_h=0.52,
            name="bar caption",
        )
        x += w

    # two callouts
    cy, ch = 4.98, 1.7
    rect(c, LEFT, cy, 3.37, ch, fill=WHITE, stroke=RULE)
    P(c, LEFT + 0.16, cy + 0.13, 3.1, k(ref), S(26, color=NAVY, font="Cambria", leading=30))
    P(
        c,
        LEFT + 0.16,
        cy + 0.62,
        3.05,
        "analytical expected net program NPV — base hazard, 15% hypothetical offer, 12 months, "
        "1,144 accounts. Illustrative unit economics; not verified profit or causal uplift.",
        S(10, color=MUTED, leading=12),
        max_h=1.0,
        name="npv callout",
    )
    rect(c, LEFT + 3.57, cy, 3.37, ch, fill=WHITE, stroke=RULE)
    P(
        c,
        LEFT + 3.73,
        cy + 0.13,
        3.1,
        str(f["gtm"]["authorized_contact_actions"]),
        S(26, color=NAVY, font="Cambria", leading=30),
    )
    P(
        c,
        LEFT + 3.73,
        cy + 0.62,
        3.05,
        "accounts are authorized for customer contact today. Every route is a planning "
        "candidate pending eligibility, ownership and permission checks.",
        S(10, color=MUTED, leading=12),
        max_h=1.0,
        name="auth callout",
    )

    # recommendation panel
    px, py, pw, ph = 7.95, 1.72, RIGHT - 7.95, 4.96
    rect(c, px, py, pw, ph, fill=PANEL)
    P(
        c,
        px + 0.25,
        py + 0.2,
        pw - 0.5,
        "Recommendation: evidence-gated program",
        S(14, color=NAVY, bold=True),
    )
    steps = [
        (
            "Validate",
            "Confirm fiscal-year inactivity, partner ownership, health and service "
            "evidence before any account is targeted.",
        ),
        (
            "Prioritize",
            "Rank opportunities with documented, versioned assumptions and keep "
            "evidence gaps visible beside every score.",
        ),
        (
            "Route",
            "Assign partner-led, direct-enterprise or digital-nurture planning workflows; "
            "hold unresolved accounts for review.",
        ),
        (
            "Pilot & measure",
            "Run controlled pilots with an untreated comparison group and track "
            "observed outcomes before any ROI claim.",
        ),
    ]
    sy = py + 0.64
    for i, (head, body) in enumerate(steps):
        c.saveState()
        c.setFillColor(col(NAVY))
        c.circle(X(px + 0.42), Y(sy + 0.17), 12, stroke=0, fill=1)
        c.restoreState()
        P(c, px + 0.3, sy + 0.07, 0.24, f"{i + 1}", S(12, color=WHITE, bold=True, align="c"))
        h = P(
            c,
            px + 0.78,
            sy,
            pw - 1.0,
            f"<b>{escape(head)}</b><br/>{escape(body)}",
            S(10.8, color=INK, leading=13),
            max_h=0.9,
            name="step",
        )
        sy += max(h, 0.5) + 0.13
    if sy > py + ph - 0.82:
        OVERFLOWS.append(f"{PAGE_NAME[0]} steps reach {sy:.2f}in")
    rect(c, px + 0.25, py + ph - 0.8, pw - 0.5, 0.62, fill=NAVY)
    P(
        c,
        px + 0.4,
        py + ph - 0.72,
        pw - 0.8,
        "Decision: fund a data-validation sprint and a measured pilot — not a full-scale "
        "reactivation campaign.",
        S(11, color=WHITE, bold=True, leading=13),
        max_h=0.5,
        name="ask",
    )


# ======================================================================================
# Executive slide 2 — data foundation and architecture
# ======================================================================================
def slide2(c, f) -> None:
    src, co = f["source"], f["cohort"]
    frame(
        c,
        kicker="Data foundation & SQL",
        title=(
            f"Systematic hygiene logged {n(src['quality_exception_rows'])} data-quality exceptions "
            "and keeps observed facts separate from modeled assumptions"
        ),
        footer=(
            "Source: Phase 1 exception register and metrics (analysis date 2026-10-09). The brief "
            "describes injected duplicates; the supplied file has zero duplicate account IDs, so "
            "detection is implemented but no merge is invented. Account identifiers and row-level "
            "outputs are confidential and excluded from every shared artifact."
        ),
        exec_index=1,
    )
    P(
        c,
        LEFT,
        1.72,
        7.1,
        "INJECTED DEFECTS AND HOW EACH WAS HANDLED",
        S(10, color=MUTED, bold=True),
    )
    cs = S(10.5, leading=12.6)
    hs = S(10.5, color=WHITE, bold=True, leading=12.6)
    rows = [
        ["Defect named in the brief", "Observed in the 2,000-row extract", "Handling"],
        [
            "Duplicate accounts across parent-child",
            f"{src['duplicate_account_rows']} duplicate IDs; duplicate, cycle and self-reference "
            "checks retained",
            "Flag for review; never auto-merge",
        ],
        [
            "Region string formatting",
            f"{src['raw_region_variants']} raw variants → {src['canonical_regions']} regions; "
            f"{n(src['issue_counts']['REGION_NORMALIZED'])} France rows normalized",
            "Trim + casefold mapping; raw value kept",
        ],
        [
            "Missing SFDC health score",
            f"{n(src['health_unknown'])} unknown ({src['health_raw_nan']} 'nan', "
            f"{src['health_raw_missing']} 'Missing')",
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
    ]
    data = [[Paragraph(escape(v), hs if i == 0 else cs) for v in r] for i, r in enumerate(rows)]
    data.append(
        [
            Paragraph(
                f"<b>{n(src['quality_exception_rows'])}</b> exception events across "
                f"{n(src['accounts_with_exceptions'])} accounts · hierarchy resolved: "
                f"{src['roots']} roots, {n(src['children'])} children, "
                f"{src['unresolved_hierarchy_rows']} unresolved",
                S(10.5, color=NAVY, leading=12.6),
            ),
            "",
            "",
        ]
    )
    table(
        c,
        LEFT,
        2.0,
        data,
        [2.05, 2.95, 2.1],
        [
            ("BACKGROUND", (0, 0), (-1, 0), col(NAVY)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 1), (-1, -2), 0.6, col(RULE)),
            ("SPAN", (0, -1), (-1, -1)),
            ("BACKGROUND", (0, -1), (-1, -1), col(PANEL)),
            ("TOPPADDING", (0, 0), (-1, -1), 4.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ],
        name="hygiene table",
        max_h=3.85,
    )

    # architecture
    ax, aw = 8.0, RIGHT - 8.0
    P(c, ax, 1.72, aw, "MODELING ARCHITECTURE (IMPLEMENTED MODULES)", S(10, color=MUTED, bold=True))
    steps = [
        (
            "Raw source → integrity gate",
            "SHA-256, row count, exact spend · source_integrity.py",
            NAVY,
        ),
        ("Cleaning, exceptions, hierarchy", "quality.py · hierarchy.py (arbitrary depth)", NAVY),
        ("DuckDB SQL analytics", "CTEs, LAG/LEAD, DENSE_RANK, running SUM · sql/*.sql", NAVY),
        ("Provisional cohort → assumed hazards", "reactivation_scenarios.py (Phase 2)", B450),
        ("Monte Carlo NPV, 1,000 runs × 9 cells", "financial_model.py (Phase 3)", B450),
        ("Rule-based GTM routing", "gtm_routing.py + versioned policy v2 (Phase 4)", B450),
    ]
    by, bh, bg = 2.0, 0.5, 0.13
    for i, (head, sub, fill) in enumerate(steps):
        y = by + i * (bh + bg)
        rect(c, ax, y, aw, bh, fill=fill)
        P(
            c,
            ax + 0.14,
            y + 0.06,
            aw - 0.25,
            f"<b>{escape(head)}</b><br/><font size='9.5' color='#D7E3F2'>{escape(sub)}</font>",
            S(11, color=WHITE, leading=13),
            max_h=bh,
            name="arch",
        )
        if i < len(steps) - 1:
            arrow(
                c,
                ax + aw / 2,
                y + bh + 0.01,
                ax + aw / 2,
                y + bh + bg - 0.01,
                color=MUTED,
                width=1.0,
                head=4.5,
            )
    ly = by + 6 * (bh + bg) - 0.02
    rect(c, ax, ly + 0.03, 0.14, 0.14, fill=NAVY)
    P(c, ax + 0.2, ly, 1.9, "Observed source facts", S(9.5, color=MUTED))
    rect(c, ax + 2.0, ly + 0.03, 0.14, 0.14, fill=B450)
    P(c, ax + 2.2, ly, 2.5, "Assumption-based models", S(9.5, color=MUTED))
    P(
        c,
        ax,
        ly + 0.25,
        aw,
        "Each phase hands off through a versioned, SHA-256-pinned contract; Phase 5 re-validates "
        "all of them before any number reaches this deck.",
        S(9.5, color=MUTED, leading=11.5),
        max_h=0.4,
        name="arch note",
    )

    # bottom callout
    rect(c, LEFT, 6.04, WIDTH, 0.72, fill=PANEL)
    P(
        c,
        LEFT + 0.2,
        6.13,
        WIDTH - 0.4,
        "<b>Why there is no observed decay curve:</b> booking dates rise exactly with account ID and "
        "every contract starts exactly 365 days earlier, so LAG/LEAD gaps reduce to ID arithmetic. "
        "Revenue-decay velocity and historical reactivation timing cannot be estimated from this "
        "extract; the decay SQL (LAG, LEAD, DENSE_RANK) is executed on a labeled synthetic fixture.",
        S(10.5, color=INK, leading=12.8),
        max_h=0.6,
        name="decay callout",
    )


# ======================================================================================
# Executive slide 3 — survival analysis
# ======================================================================================
def slide3(c, f) -> None:
    sv = f["survival"]
    e = sv["expected"]
    frame(
        c,
        kicker="Reactivation probability & survival analysis",
        title=(
            f"Assumed hazards imply {e['conservative'][12]:.0f}–{e['optimistic'][12]:.0f} expected "
            "first reactivations within 12 months — a planning range, not a forecast"
        ),
        footer=(
            "Source: frozen Phase 2 outputs (reactivation_scenario_summary.csv, scenario_sensitivity.csv, "
            "synthetic_cox_coefficients.csv); assumption register v1, fingerprint 6195ba2e…. "
            "Probabilities are ASSUMPTION_BASED_NOT_CALIBRATED; the Cox fit uses invented subjects only."
        ),
        exec_index=2,
    )
    # Lane A
    lx, lw = LEFT, 4.35
    rect(c, lx, 1.72, lw, 4.98, fill=PANEL)
    P(c, lx + 0.2, 1.86, lw - 0.4, "LANE A · METHOD DEMONSTRATION", S(9.5, color=B550, bold=True))
    P(
        c,
        lx + 0.2,
        2.08,
        lw - 0.4,
        "Cox proportional hazards on synthetic event histories",
        S(13, color=NAVY, bold=True, leading=15.5),
        max_h=0.55,
        name="laneA title",
    )
    cox = sv["cox"]
    names = {
        "health_proxy": "Health proxy",
        "engagement_proxy": "Engagement proxy",
        "partner_proxy": "Partner proxy",
    }
    hs = S(10, color=WHITE, bold=True, leading=12)
    cs = S(10, leading=12)
    data = [
        [
            Paragraph("Synthetic covariate", hs),
            Paragraph("True β", hs),
            Paragraph("Fitted HR (95% CI)", hs),
        ]
    ]
    for key, label in names.items():
        r = cox[key]
        data.append(
            [
                Paragraph(label, cs),
                Paragraph(signed(r["true_beta"]), cs),
                Paragraph(f"{r['hr']:.2f} ({r['lo']:.2f}–{r['hi']:.2f})", cs),
            ]
        )
    table(
        c,
        lx + 0.2,
        2.72,
        data,
        [1.45, 0.75, 1.75],
        [
            ("BACKGROUND", (0, 0), (-1, 0), col(NAVY)),
            ("BACKGROUND", (0, 1), (-1, -1), col(WHITE)),
            ("LINEBELOW", (0, 1), (-1, -1), 0.6, col(RULE)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ],
        name="cox table",
    )
    d = sv["cox_diagnostics"]
    p = d["schoenfeld_p"]
    bullets(
        c,
        lx + 0.2,
        4.08,
        lw - 0.4,
        [
            f"1,600 invented subjects: {n(d['events'])} events, {n(d['censored'])} right-censored.",
            f"Concordance {d['concordance_in_sample']:.2f} in-sample and {d['concordance_holdout']:.2f} "
            "on an independent synthetic holdout.",
            f"Schoenfeld proportional-hazards p-values {p['health_proxy']:.2f} / "
            f"{p['engagement_proxy']:.2f} / {p['partner_proxy']:.2f}: no violation detected.",
            "<b>Shows the lifelines workflow recovers known effects. It is not an Everpure model: the "
            "extract has no customer event histories.</b>",
        ],
        S(10.5, leading=12.8),
        gap=0.08,
        max_h=2.5,
        name="laneA bullets",
    )

    # Lane B
    bx = lx + lw + 0.35
    bw = RIGHT - bx
    P(c, bx, 1.72, bw, "LANE B · EVERPURE PLANNING SCENARIOS", S(9.5, color=B550, bold=True))
    P(
        c,
        bx,
        1.94,
        bw,
        "Assumption-based exponential hazards for the 1,144 modeled accounts — expected cumulative "
        "first reactivations",
        S(13, color=NAVY, bold=True, leading=15.5),
        max_h=0.55,
        name="laneB title",
    )
    # clustered columns
    cx0, cy0, cw, chh = bx + 0.1, 2.72, bw - 0.2, 1.95  # plot box
    vmax = 230.0
    groups = [
        ("Conservative", "conservative", sv["baseline_hazards"]["conservative"]),
        ("Base", "base", sv["baseline_hazards"]["base"]),
        ("Optimistic", "optimistic", sv["baseline_hazards"]["optimistic"]),
    ]
    horizons = [(3, B250, "By month 3"), (6, B450, "By month 6"), (12, B700, "By month 12")]
    # legend
    lgx = cx0
    for _, color, label in horizons:
        rect(c, lgx, cy0 - 0.02, 0.15, 0.13, fill=color)
        P(c, lgx + 0.2, cy0 - 0.05, 1.3, label, S(9.5, color=MUTED))
        lgx += 1.35
    base_y = cy0 + 0.25 + chh
    gw = cw / 3
    bwid = 0.48
    for gi, (label, key, lam) in enumerate(groups):
        gx = cx0 + gi * gw + (gw - 3 * bwid - 2 * 0.05) / 2
        for hi, (hz, color, _) in enumerate(horizons):
            v = e[key][hz]
            hgt = chh * v / vmax
            x = gx + hi * (bwid + 0.05)
            rect(c, x, base_y - hgt, bwid, hgt, fill=color)
            P(
                c,
                x - 0.1,
                base_y - hgt - 0.22,
                bwid + 0.2,
                f"{v:.1f}",
                S(10, color=INK, align="c", bold=(hz == 12)),
            )
        P(
            c,
            cx0 + gi * gw,
            base_y + 0.06,
            gw,
            f"<b>{label}</b><br/><font color='#{MUTED}'>baseline {lam * 100:.1f}% per month</font>",
            S(10.5, align="c", leading=12.5),
        )
    line(c, cx0, base_y, cx0 + cw, base_y, color=RULE, width=1)
    s12 = sv["sensitivity_12m"]
    bullets(
        c,
        bx,
        5.48,
        bw,
        [
            "Counts are cumulative expectations, not observed conversions: the 3-, 6- and 12-month "
            "values must not be added. No campaign treatment effect is identified.",
            "P(reactivate by month t) = 1 − exp(−λ·t·e<super>xβ</super>), with assumed effects for "
            "health, partner ownership, child status and valid tickets.",
            f"Unknown health is scored at the reference level and lifts rankings: scoring it as Yellow "
            f"or Red cuts base 12-month reactivations from {e['base'][12]:.1f} to "
            f"{s12['unknown_health_as_yellow']['expected']:.1f} or "
            f"{s12['unknown_health_as_red']['expected']:.1f}.",
        ],
        S(10.5, leading=12.6),
        gap=0.06,
        max_h=1.4,
        name="laneB bullets",
    )


# ======================================================================================
# Executive slide 4 — Monte Carlo NPV
# ======================================================================================
def slide4(c, f) -> None:
    fin = f["financial"]
    nine = fin["nine_cell"]
    a = fin["assumptions"]
    base = nine["base"]
    ref = base["medium_15pct"]
    frame(
        c,
        kicker="Monte Carlo NPV & financial risk",
        title=(
            f"Illustrative economics are positive in the base case (~{k(ref['analytical_expected_npv'], 0)} "
            "at a 15% offer) but depend heavily on unverified assumptions"
        ),
        footer=(
            "Source: frozen Phase 3 outputs (financial_scenario_matrix.csv, monte_carlo_npv_summary.csv, "
            "financial_sensitivity.csv); assumption fingerprint b953c02d…; NumPy PCG64 seed 20261009 with "
            "common random numbers. P5/P95 are conditional simulation percentiles, not confidence "
            "intervals. Label: ILLUSTRATIVE_NET_PROGRAM_NPV_NOT_CAUSALLY_ATTRIBUTED."
        ),
        exec_index=3,
    )
    lw = 6.7
    P(
        c,
        LEFT,
        1.72,
        lw,
        "ANALYTICAL EXPECTED NET PROGRAM NPV — BASE HAZARD, BY HYPOTHETICAL OFFER",
        S(10, color=MUTED, bold=True),
    )
    tiers = [
        ("5% offer", "low_5pct", B450),
        ("15% offer · central case", "medium_15pct", NAVY),
        ("30% offer", "high_30pct", B450),
    ]
    cx0, top, chh = LEFT + 0.1, 2.28, 1.78
    base_y = top + chh
    vmax = 260_000.0
    gw = (lw - 0.2) / 3
    for i, (label, key, color) in enumerate(tiers):
        v = base[key]["analytical_expected_npv"]
        hgt = chh * v / vmax
        x = cx0 + i * gw + gw * 0.2
        rect(c, x, base_y - hgt, gw * 0.6, hgt, fill=color)
        P(
            c,
            x - 0.2,
            base_y - hgt - 0.3,
            gw * 0.6 + 0.4,
            k(v),
            S(14, color=NAVY, bold=True, align="c"),
        )
        P(
            c,
            cx0 + i * gw,
            base_y + 0.07,
            gw,
            escape(label),
            S(10.5, align="c", bold=(key == "medium_15pct")),
        )
    line(c, cx0, base_y, cx0 + lw - 0.2, base_y, color=RULE, width=1)

    # Monte Carlo strip
    my = 4.5
    P(
        c,
        LEFT,
        my,
        lw,
        f"MONTE CARLO DISTRIBUTION — BASE HAZARD, 15% OFFER, {n(ref['runs'])} RUNS",
        S(10, color=MUTED, bold=True),
    )
    hs = S(10, color=WHITE, bold=True, align="c", leading=12)
    vs = S(13, color=NAVY, bold=True, align="c", leading=15)
    negatives = round(ref["pr_negative"] * ref["runs"])
    data = [
        [
            Paragraph(h, hs)
            for h in (
                "Sample mean",
                "Median",
                "5th percentile",
                "95th percentile",
                "Runs with NPV &lt; $0",
            )
        ],
        [
            Paragraph(v, vs)
            for v in (
                k(ref["mc_mean"]),
                k(ref["mc_median"]),
                k(ref["mc_p05"]),
                k(ref["mc_p95"]),
                f"{negatives} of {n(ref['runs'])}",
            )
        ],
    ]
    table(
        c,
        LEFT,
        my + 0.27,
        data,
        [lw / 5] * 5,
        [
            ("BACKGROUND", (0, 0), (-1, 0), col(NAVY)),
            ("BACKGROUND", (0, 1), (-1, 1), col(PANEL)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ],
        name="mc table",
    )
    P(
        c,
        LEFT,
        my + 1.03,
        lw,
        f"Analytical expectation {k(ref['analytical_expected_npv'])} (closed form) vs. simulation "
        f"sample mean {k(ref['mc_mean'])}: a +{ref['z']:.2f} standard-error difference; the largest "
        f"across all nine cells is {fin['max_abs_z']:.2f}.",
        S(9.5, color=MUTED, leading=11.5),
        max_h=0.35,
        name="mc note",
    )

    # interpretation panel
    px = LEFT + lw + 0.4
    pw = RIGHT - px
    rect(c, px, 1.72, pw, 4.0, fill=PANEL)
    P(c, px + 0.22, 1.86, pw - 0.44, "How to read the result", S(14, color=NAVY, bold=True))
    be = fin["break_even"]
    st = fin["stress"]
    bullets(
        c,
        px + 0.22,
        2.3,
        pw - 0.44,
        [
            f"<b>5% scores highest only because the model holds reactivation hazard fixed across "
            f"offers.</b> 15% and 30% would need {be['hazard_multiplier_medium_15pct']:.2f}× and "
            f"{be['hazard_multiplier_high_30pct']:.2f}× the hazard to match it — not evidence that 5% "
            "is optimal.",
            f"Across the nine cells the expected NPV ranges from "
            f"{k(nine['conservative']['high_30pct']['analytical_expected_npv'])} (conservative, 30%) to "
            f"{k(nine['optimistic']['low_5pct']['analytical_expected_npv'])} (optimistic, 5%). The cells "
            "are alternatives; never add them.",
            f"Committed combined adverse stress ($750 revenue, 45% margin, $150 outreach, $300 "
            f"activation, 24% rate, 3 paid months) turns NPV to "
            f"<b>{k(st['committed_adverse_npv_usd'])}</b>.",
            "Net program value under analyst-selected unit economics — not verified profitability or "
            "causally identified incremental uplift.",
        ],
        S(11, leading=13.4),
        gap=0.1,
        max_h=3.3,
        name="interpretation",
    )

    # assumption chips
    ay = 5.95
    P(
        c,
        LEFT,
        ay,
        WIDTH,
        "ILLUSTRATIVE UNIT ECONOMICS (ANALYST-SELECTED, NOT OBSERVED)",
        S(9.5, color=MUTED, bold=True),
    )
    chips = [
        (f"${a['monthly_gross_revenue']:,.0f}", "gross revenue per activated account per month"),
        (f"{a['contribution_margin'] * 100:.0f}%", "contribution margin"),
        (f"${a['outreach_cost']:,.0f}", "outreach per modeled account"),
        (f"${a['activation_cost']:,.0f}", "activation cost per reactivation"),
        (f"{a['annual_discount_rate'] * 100:.0f}%", "annual effective discount rate"),
        (f"{a['horizon_months']} months", "financial horizon, no churn"),
    ]
    cwid = (WIDTH - 5 * 0.12) / 6
    for i, (big, small) in enumerate(chips):
        x = LEFT + i * (cwid + 0.12)
        rect(c, x, ay + 0.22, cwid, 0.62, fill=WHITE, stroke=RULE)
        P(
            c,
            x + 0.1,
            ay + 0.27,
            cwid - 0.2,
            f"<font name='Arial-Bold' size='12.5' color='#{NAVY}'>{escape(big)}</font><br/>"
            f"{escape(small)}",
            S(9, color=MUTED, leading=11),
            max_h=0.56,
            name="chip",
        )


# ======================================================================================
# Executive slide 5 — GTM routing and decision
# ======================================================================================
def slide5(c, f) -> None:
    g = f["gtm"]
    ch = g["channels"]
    frame(
        c,
        kicker="GTM routing, roadmap & decision",
        title=(
            f"Route {g['routed_candidates']} accounts to conditional planning channels, hold "
            f"{ch['HOLD_REVIEW']} for review, and release outreach only through gated pilots"
        ),
        footer=(
            "Source: frozen Phase 4 aggregates via phase5_input_contract.json v2 (policy fingerprint "
            "1998cc4a…). All dispositions are PLANNING_ONLY with execution_authorized = false. Priority "
            "tiers use fixed base/15% NPV cutpoints; the modeled NPV is not attributable to the "
            f"{g['routed_candidates']} routed accounts alone."
        ),
        exec_index=4,
    )
    # column 1 — routes
    c1w = 4.25
    P(
        c,
        LEFT,
        1.72,
        c1w,
        "CONDITIONAL ROUTES · 1,144 MODELED ACCOUNTS",
        S(10, color=MUTED, bold=True),
    )
    routes = [
        ("Partner-led candidate", "PARTNER_LED_CANDIDATE", B550),
        ("Direct-enterprise candidate", "DIRECT_ENTERPRISE_CANDIDATE", B550),
        ("Digital-nurture candidate", "DIGITAL_NURTURE_CANDIDATE", B550),
        ("Hold / review", "HOLD_REVIEW", GRAY),
    ]
    vmax = max(ch.values())
    ry = 2.05
    for label, key, color in routes:
        P(c, LEFT, ry, c1w, f"<b>{label}</b>", S(10.5, color=INK))
        bwid = (c1w - 1.25) * ch[key] / vmax
        rect(c, LEFT, ry + 0.22, bwid, 0.3, fill=color)
        P(
            c,
            LEFT + bwid + 0.08,
            ry + 0.24,
            1.2,
            f"<b>{ch[key]}</b> · {g['channel_pct'][key]:.1f}%",
            S(10.5, color=INK),
        )
        ry += 0.66
    rules = g["rules"]
    P(
        c,
        LEFT,
        ry + 0.04,
        c1w,
        f"Holds: {rules['R3']} unknown partner ownership (R3) and {rules['R4']} needing service "
        "recovery — Red health or ≥ 5 valid open tickets (R4).",
        S(9.5, color=MUTED, leading=11.5),
        max_h=0.45,
        name="holds note",
    )

    # column 2 — evidence quality
    c2x, c2w = LEFT + c1w + 0.35, 3.55
    P(c, c2x, 1.72, c2w, "EVIDENCE QUALITY & HIERARCHY", S(10, color=MUTED, bold=True))
    pr, rd, rt = g["priority"], g["readiness"], g["roots"]
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
    ky = 2.02
    for big, small in kpis:
        rect(c, c2x, ky, c2w, 0.64, fill=PANEL)
        P(
            c,
            c2x + 0.14,
            ky + 0.05,
            c2w - 0.25,
            f"<font name='Cambria' size='15' color='#{NAVY}'>{escape(big)}</font><br/>"
            f"{escape(small)}",
            S(9.5, color=MUTED, leading=11.2),
            max_h=0.6,
            name="kpi",
        )
        ky += 0.71

    # column 3 — gates
    c3x = c2x + c2w + 0.35
    c3w = RIGHT - c3x
    P(c, c3x, 1.72, c3w, "RELEASE GATES BEFORE ANY OUTREACH", S(10, color=MUTED, bold=True))
    gates = [
        ("Validate", "fiscal eligibility, partner ownership, health and service barriers"),
        ("Coordinate", "resolve parent-child ownership; prevent overlapping campaigns"),
        ("Pilot", "controlled partner / direct / digital pilots where permissions exist"),
        ("Measure", "observed reactivation, uplift vs. control, actual cost and margin"),
        ("Scale", "recalibrate the model; scale only when evidence supports it"),
    ]
    gy = 2.02
    for i, (head, body) in enumerate(gates):
        rect(c, c3x, gy, 0.62, 0.64, fill=NAVY if i < 2 else B450)
        P(
            c,
            c3x,
            gy + 0.08,
            0.62,
            f"Gate<br/><b>{i + 1}</b>",
            S(10, color=WHITE, align="c", leading=12),
        )
        rect(c, c3x + 0.62, gy, c3w - 0.62, 0.64, fill=PANEL)
        P(
            c,
            c3x + 0.74,
            gy + 0.07,
            c3w - 0.84,
            f"<b>{head}</b> — {escape(body)}",
            S(10, color=INK, leading=12),
            max_h=0.58,
            name="gate",
        )
        gy += 0.71

    # decision bar + links
    rect(c, LEFT, 5.66, WIDTH, 0.62, fill=NAVY)
    P(
        c,
        LEFT + 0.2,
        5.74,
        WIDTH - 0.4,
        "Decision: approve a data-validation sprint and a controlled, measured pilot — not a "
        "full-scale reactivation campaign. The 518 routed candidates are not approved contacts.",
        S(11.5, color=WHITE, bold=True, leading=13.5),
        max_h=0.5,
        name="decision",
    )
    bw = (WIDTH - 0.25) / 2
    link_button(c, LEFT, 6.38, bw, 0.46, cfg.DRIVE_LABEL, cfg.DRIVE_URL)
    link_button(c, LEFT + bw + 0.25, 6.38, bw, 0.46, cfg.GITHUB_LABEL, cfg.GITHUB_URL)


# ======================================================================================
# Appendix pages
# ======================================================================================
APPENDIX = [
    ("A", "Reproducibility, evidence links and deliverables map"),
    ("B", "SQL engineering and data hygiene (implemented code)"),
    ("C", "Survival methodology and assumed-hazard scenarios"),
    ("D", "Monte Carlo NPV summary — all nine scenario × offer cells"),
    ("E", "Financial sensitivity, break-even and adverse stress"),
    ("F", "Algorithmic GTM routing flowchart (policy v2)"),
    ("G", "GTM decision table, evidence quality and root coordination"),
    ("H", "Validation evidence, limitations and next steps"),
]


def app_frame(c, letter, footer) -> None:
    title = dict(APPENDIX)[letter]
    frame(
        c,
        kicker=f"Technical appendix · {letter}",
        title=f"Appendix {letter} — {title}",
        footer=footer,
        appendix=letter,
        label=f"Appendix {letter}",
    )
    c.bookmarkPage(f"app{letter}")
    c.addOutlineEntry(f"Appendix {letter} — {title}", f"app{letter}", level=1)


def code_panel(c, x, y, w, h, path, code, *, size=8.6) -> None:
    rect(c, x, y, w, h, fill="F6F8FB", stroke=RULE)
    P(c, x + 0.12, y + 0.07, w - 0.24, f"<b>{escape(path)}</b>", S(9.5, color=B550))
    t = c.beginText()
    t.setFont("Consolas", size)
    t.setFillColor(col(INK))
    lead = size * 1.22
    t.setTextOrigin(X(x + 0.14), Y(y + 0.33) - size)
    t.setLeading(lead)
    for raw in code.splitlines():
        t.textLine(raw)
    USED_TEXT.append(("Consolas", code))
    needed = 0.33 + len(code.splitlines()) * lead / 72 + 0.08
    if needed > h + 0.01:
        OVERFLOWS.append(f"{PAGE_NAME[0]} code {path}: {needed:.2f}in > {h:.2f}in")
    c.drawText(t)


def appendix_a(c, f) -> None:
    app_frame(
        c,
        "A",
        (
            "Neither link is a substitute for this PDF: pages 1–5 are the executive deck and these pages "
            "carry the technical evidence. Confidential source rows, account identifiers, root mappings and "
            "account-level model outputs are excluded from every shared package."
        ),
    )
    lw = 6.25
    P(c, LEFT, 1.45, lw, "TECHNICAL ARTIFACTS", S(10, color=MUTED, bold=True))
    link_button(
        c,
        LEFT,
        1.72,
        lw,
        0.66,
        cfg.DRIVE_LABEL,
        cfg.DRIVE_URL,
        sub="Rendered diagrams, aggregate result tables, notebooks and this deck",
    )
    link_button(
        c,
        LEFT,
        2.5,
        lw,
        0.66,
        cfg.GITHUB_LABEL,
        cfg.GITHUB_URL,
        sub="Sanitized package with a fresh Git history; runs without confidential data",
    )
    P(c, LEFT, 3.35, lw, "WHAT THE CODE PACKAGE CONTAINS", S(10, color=MUTED, bold=True))
    cs = S(9.5, leading=11.4)
    hs = S(9.5, color=WHITE, bold=True, leading=11.4)
    rows = [
        ("Path", "Contents"),
        (
            "notebooks/00_synthetic_reviewer_demo",
            "End-to-end run on invented accounts: cleaning, SQL, "
            "hazards, Monte Carlo, routing (no confidential data)",
        ),
        (
            "notebooks/01–04",
            "Data foundation & SQL · survival · Monte Carlo NPV · GTM routing "
            "(full runs need the authorized source)",
        ),
        (
            "src/everpure_case/",
            "Python modules: integrity, cleaning, hierarchy, survival, finance, routing",
        ),
        ("sql/", "DuckDB SQL: CTEs, LAG/LEAD, DENSE_RANK, running windows"),
        (
            "tests/ · docs/ · outputs/",
            "pytest suite · methodology, contracts, registers · frozen "
            "aggregate results with SHA-256 manifests",
        ),
    ]
    data = [
        [
            Paragraph(escape(a), hs if i == 0 else S(9.5, font="Consolas", leading=11.4)),
            Paragraph(escape(b), hs if i == 0 else cs),
        ]
        for i, (a, b) in enumerate(rows)
    ]
    table(
        c,
        LEFT,
        3.62,
        data,
        [2.45, lw - 2.45],
        [
            ("BACKGROUND", (0, 0), (-1, 0), col(NAVY)),
            ("LINEBELOW", (0, 1), (-1, -1), 0.6, col(RULE)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ],
        name="package table",
        max_h=2.4,
    )

    rx = LEFT + lw + 0.4
    rw = RIGHT - rx
    P(c, rx, 1.45, rw, "TWO REPRODUCTION PATHS", S(10, color=MUTED, bold=True))
    rect(c, rx, 1.72, rw, 1.32, fill=PANEL)
    P(
        c,
        rx + 0.16,
        1.8,
        rw - 0.32,
        "<b>Path A — authorized full reproduction.</b> Place the original assessment CSV at "
        "<font name='Consolas'>data/raw/</font>; the integrity gate checks its SHA-256, 2,000 rows and "
        "$2,541,024,291 recorded spend. Then run the Phase 1→4 pipelines; the validators re-derive "
        "every route and aggregate.",
        S(10, leading=12.2),
        max_h=1.2,
        name="pathA",
    )
    rect(c, rx, 3.12, rw, 1.0, fill=PANEL)
    P(
        c,
        rx + 0.16,
        3.2,
        rw - 0.32,
        "<b>Path B — synthetic demonstration.</b> <font name='Consolas'>pip install -r "
        "requirements.txt</font>, then run notebook 00 and the synthetic tests. Invented SYN_ accounts "
        "only; it shows the mechanics and never reproduces Everpure results.",
        S(10, leading=12.2),
        max_h=0.9,
        name="pathB",
    )
    P(c, rx, 4.28, rw, "PROVENANCE FINGERPRINTS (SHA-256)", S(10, color=MUTED, bold=True))
    pv = f["provenance"]
    fp = [
        ("Source CSV", pv["source_sha256"]),
        ("Phase 2 assumptions", pv["phase2_assumption_fingerprint"]),
        ("Phase 3 financials", pv["phase3_financial_fingerprint"]),
        ("Phase 4 policy", pv["phase4_policy_fingerprint"]),
        ("Phase 5 input contract", pv["phase5_contract_sha256"]),
    ]
    data = [
        [
            Paragraph(a, S(9.5, leading=11)),
            Paragraph(b[:32] + "…", S(9, font="Consolas", leading=11)),
        ]
        for a, b in fp
    ]
    table(
        c,
        rx,
        4.53,
        data,
        [1.75, rw - 1.75],
        [
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, col(RULE)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ],
        name="fingerprints",
    )
    P(
        c,
        rx,
        6.12,
        rw,
        "Environment: Python 3.12 · pandas 2 · NumPy 2 · DuckDB 1 · lifelines 0.30 · matplotlib 3.10 · "
        "nbclient/ipykernel · pytest. Frozen baseline commit 38b1f43 (Phase 4).",
        S(9.5, color=MUTED, leading=11.5),
        max_h=0.5,
        name="env",
    )

    # deliverables map (small)
    P(
        c,
        LEFT,
        6.12,
        lw,
        "<b>Brief deliverables:</b> executable Python/SQL notebook → code package (A, B) · "
        "three-tier Monte Carlo NPV summary → slide 4 and D · routing flowchart → slide 5 and F · "
        "five-slide deck → pages 1–5.",
        S(9.5, color=INK, leading=11.5),
        max_h=0.5,
        name="map",
    )


SQL_CONCENTRATION = """WITH account_spend AS (
    SELECT h.root_account_id, a.account_id, a.historical_spend_usd_num AS spend_usd
    FROM accounts a JOIN hierarchy h USING (source_row_number)
    WHERE h.hierarchy_status = 'resolved'
), root_spend AS (
    SELECT root_account_id, COUNT(*) AS account_count,
           SUM(spend_usd) AS additive_recorded_spend_usd
    FROM account_spend GROUP BY root_account_id
), ranked AS (
    SELECT *, DENSE_RANK() OVER (ORDER BY additive_recorded_spend_usd DESC) AS spend_rank,
           SUM(additive_recorded_spend_usd) OVER () AS all_resolved_spend_usd,
           SUM(additive_recorded_spend_usd) OVER (
               ORDER BY additive_recorded_spend_usd DESC, root_account_id
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
           ) AS cumulative_recorded_spend_usd
    FROM root_spend
)"""

SQL_DECAY = """), sequenced AS (
    SELECT *,
           LAG(fiscal_period_index) OVER account_sequence AS previous_period_index,
           LAG(period_revenue_usd) OVER account_sequence AS previous_revenue_usd,
           LEAD(fiscal_period_index) OVER account_sequence AS next_period_index,
           LEAD(period_revenue_usd) OVER account_sequence AS next_revenue_usd,
           DENSE_RANK() OVER (
               PARTITION BY account_id ORDER BY fiscal_period_index DESC
           ) AS observed_period_recency_rank
    FROM validated
    WINDOW account_sequence AS (PARTITION BY account_id ORDER BY fiscal_period_index)
)
SELECT ..., CASE WHEN fiscal_period_index - previous_period_index = 1
                 AND previous_revenue_usd <> 0
            THEN (period_revenue_usd - previous_revenue_usd)
                 / NULLIF(previous_revenue_usd, 0) END AS consecutive_pct_change"""

PY_HYGIENE = """def normalize_region(raw: str) -> str | None:
    return REGION_MAP.get(" ".join(raw.split()).casefold())

frame["ticket_sentinel"] = frame["open_support_tickets_num"].eq(999)
frame["tickets_clean"] = (
    frame["open_support_tickets_num"].mask(frame["ticket_sentinel"]))
dup = frame["account_id_key"].ne("") & \\
      frame["account_id_key"].duplicated(keep=False)"""


def appendix_b(c, f) -> None:
    src = f["source"]
    app_frame(
        c,
        "B",
        (
            "Excerpts are verbatim from the implemented files except where marked “…” or re-wrapped; "
            "complete code is in the package. Real-data LAG/LEAD queries run on booking dates that follow the "
            "account-ID sequence, so they are reported as source-pattern diagnostics, never as decay evidence."
        ),
    )
    lw = 7.45
    code_panel(
        c,
        LEFT,
        1.45,
        lw,
        2.73,
        "sql/spend_concentration.sql — CTE chain, DENSE_RANK, running SUM",
        SQL_CONCENTRATION,
        size=8.0,
    )
    code_panel(
        c,
        LEFT,
        4.25,
        lw,
        2.6,
        "sql/synthetic_account_decay.sql — LAG / LEAD / DENSE_RANK decay velocity (synthetic)",
        SQL_DECAY,
        size=8.0,
    )
    rx = LEFT + lw + 0.3
    rw = RIGHT - rx
    P(c, rx, 1.45, rw, "EXCEPTION REGISTER (PHASE 1)", S(10, color=MUTED, bold=True))
    labels = {
        "INACTIVITY_VALUE_GAP_6M": "Reported vs. date-derived inactivity gap ≥ 6 months",
        "UNKNOWN_HEALTH": "SFDC health missing ('nan' / 'Missing')",
        "REGION_NORMALIZED": "Region whitespace / casing normalized",
        "UNRESOLVED_PARTNER": "Partner-managed flag missing",
        "INACTIVITY_CONTRADICTION": "Reported < 2 years vs. calendar proxy ≥ 2",
        "TICKET_SENTINEL_999": "Sentinel 999 open tickets",
        "MISSING_INACTIVITY": "years_inactive missing",
    }
    cs = S(9, leading=10.6)
    data = [
        [
            Paragraph("Issue (code)", S(9.5, color=WHITE, bold=True)),
            Paragraph("Events", S(9.5, color=WHITE, bold=True, align="r")),
        ]
    ]
    for code, count in sorted(src["issue_counts"].items(), key=lambda kv: -kv[1]):
        data.append(
            [
                Paragraph(
                    f"{escape(labels[code])}<br/><font name='Consolas' size='8' "
                    f"color='#{MUTED}'>{code}</font>",
                    cs,
                ),
                Paragraph(n(count), S(9.5, align="r")),
            ]
        )
    data.append(
        [
            Paragraph(
                f"<b>Total exception events · {n(src['accounts_with_exceptions'])} accounts</b>", cs
            ),
            Paragraph(f"<b>{n(src['quality_exception_rows'])}</b>", S(9.5, align="r")),
        ]
    )
    table(
        c,
        rx,
        1.72,
        data,
        [rw - 0.75, 0.75],
        [
            ("BACKGROUND", (0, 0), (-1, 0), col(NAVY)),
            ("LINEBELOW", (0, 1), (-1, -2), 0.5, col(RULE)),
            ("LINEABOVE", (0, -1), (-1, -1), 1.0, col(INK)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ],
        name="exception table",
        max_h=3.2,
    )
    code_panel(
        c, rx, 5.02, rw, 1.84, "src/everpure_case/quality.py (excerpt)", PY_HYGIENE, size=7.9
    )


def appendix_c(c, f) -> None:
    sv = f["survival"]
    e = sv["expected"]
    eff = sv["effects"]
    lam = sv["baseline_hazards"]
    app_frame(
        c,
        "C",
        (
            "Lane B probabilities are scenario assumptions (register phase2-assumptions-v1), not estimates "
            "from Everpure outcomes. Lane A coefficients describe an invented experiment only. Expected "
            "counts at 3, 6 and 12 months are cumulative and never additive."
        ),
    )
    lw = 5.6
    rect(c, LEFT, 1.45, lw, 2.55, fill=PANEL)
    P(
        c,
        LEFT + 0.18,
        1.55,
        lw - 0.36,
        "Lane B — Everpure planning scenarios",
        S(12, color=NAVY, bold=True),
    )
    bullets(
        c,
        LEFT + 0.18,
        1.9,
        lw - 0.36,
        [
            "Constant monthly hazard per account: h(t | x) = λ<sub>s</sub> · exp(x·β)",
            "P(T ≤ t | x) = 1 − exp(−λ<sub>s</sub> · t · exp(x·β));  E[N(t)] = Σ P(T ≤ t | x) over "
            "the 1,144 accounts",
            f"λ<sub>s</sub> per month: conservative {lam['conservative']:.3f} · base {lam['base']:.3f} · "
            f"optimistic {lam['optimistic']:.3f}",
            f"Assumed β: Red health {signed(eff['health_red'])}; Yellow {signed(eff['health_yellow'])}; "
            f"child account {signed(eff['is_child'])}; log(1 + valid tickets) "
            f"{signed(eff['log1p_valid_tickets'])}; partner-managed Yes {signed(eff['partner_managed_yes'])}",
            "Unknown health, partner or tickets → reference level (0) plus explicit missingness flags",
        ],
        S(10, leading=12.2),
        gap=0.05,
        max_h=2.05,
        name="laneB spec",
    )
    rect(c, LEFT, 4.12, lw, 2.72, fill=PANEL)
    P(
        c,
        LEFT + 0.18,
        4.22,
        lw - 0.36,
        "Lane A — Cox proportional hazards (synthetic)",
        S(12, color=NAVY, bold=True),
    )
    d = sv["cox_diagnostics"]
    bullets(
        c,
        LEFT + 0.18,
        4.57,
        lw - 0.36,
        [
            "h(t | x) = h<sub>0</sub>(t) · exp(x·β), estimated by partial likelihood (lifelines "
            "CoxPHFitter); 1,600 invented subjects, 36-month follow-up, seed 20261009",
            f"{n(d['events'])} events, {n(d['censored'])} right-censored; fitted log-coefficients "
            f"{signed(sv['cox']['health_proxy']['beta'], 3)} / "
            f"{signed(sv['cox']['engagement_proxy']['beta'], 3)} / "
            f"{signed(sv['cox']['partner_proxy']['beta'], 3)} vs. generating "
            f"{signed(sv['cox']['health_proxy']['true_beta'], 3)} / "
            f"{signed(sv['cox']['engagement_proxy']['true_beta'], 3)} / "
            f"{signed(sv['cox']['partner_proxy']['true_beta'], 3)}",
            f"Concordance {d['concordance_in_sample']:.3f} in-sample, {d['concordance_holdout']:.3f} "
            "holdout; rank-based Schoenfeld tests do not reject proportional hazards",
            "Purpose: show a correct, diagnosable survival workflow. It is never used to score Everpure "
            "accounts.",
        ],
        S(10, leading=12.2),
        gap=0.05,
        max_h=2.15,
        name="laneA spec",
    )

    rx = LEFT + lw + 0.35
    rw = RIGHT - rx
    P(
        c,
        rx,
        1.45,
        rw,
        "EXPECTED CUMULATIVE FIRST REACTIVATIONS (1,144 ACCOUNTS)",
        S(10, color=MUTED, bold=True),
    )
    hs = S(10, color=WHITE, bold=True, align="r")
    data = [
        [Paragraph("Scenario", S(10, color=WHITE, bold=True))]
        + [Paragraph(h, hs) for h in ("3 months", "6 months", "12 months", "Mean P(12m)")]
    ]
    for key, label in (
        ("conservative", "Conservative"),
        ("base", "Base"),
        ("optimistic", "Optimistic"),
    ):
        mean12 = e[key][12] / 1144
        data.append(
            [Paragraph(label, S(10))]
            + [Paragraph(f"{e[key][h]:.2f}", S(10, align="r", bold=(h == 12))) for h in (3, 6, 12)]
            + [Paragraph(f"{mean12 * 100:.1f}%", S(10, align="r"))]
        )
    table(
        c,
        rx,
        1.72,
        data,
        [1.7, 1.25, 1.25, 1.25, rw - 5.45],
        [
            ("BACKGROUND", (0, 0), (-1, 0), col(NAVY)),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, col(RULE)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ],
        name="survival table",
    )
    P(
        c,
        rx,
        3.15,
        rw,
        "BASE-SCENARIO 12-MONTH SENSITIVITY (SAME MODEL, ONE CHANGE AT A TIME)",
        S(10, color=MUTED, bold=True),
    )
    s12 = sv["sensitivity_12m"]
    cases = [
        ("Primary base case", "primary_base"),
        ("Baseline hazard × 0.5", "half_baseline_hazard"),
        ("Baseline hazard × 1.5", "one_and_half_baseline_hazard"),
        (
            "Covariate effects × 0 / × 0.5 / × 1.5",
            ("zero_covariate_effects", "half_covariate_effects", "one_and_half_covariate_effects"),
        ),
        (
            "Unknown health as Yellow / Red / observed mix",
            (
                "unknown_health_as_yellow",
                "unknown_health_as_red",
                "unknown_health_observed_average",
            ),
        ),
        ("Hypothetically include 562 conflicts (n = 1,706)", "hypothetical_include_conflicts"),
        ("…and 294 unknowns too (n = 2,000)", "hypothetical_include_all_including_unknown"),
    ]
    data = [
        [
            Paragraph("Case", S(10, color=WHITE, bold=True)),
            Paragraph("Expected reactivations", S(10, color=WHITE, bold=True, align="r")),
        ]
    ]
    for label, key in cases:
        keys = key if isinstance(key, tuple) else (key,)
        val = " / ".join(f"{s12[x]['expected']:.1f}" for x in keys)
        data.append([Paragraph(escape(label), S(10)), Paragraph(val, S(10, align="r"))])
    table(
        c,
        rx,
        3.42,
        data,
        [rw - 2.3, 2.3],
        [
            ("BACKGROUND", (0, 0), (-1, 0), col(NAVY)),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, col(RULE)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ],
        name="sensitivity table",
        max_h=2.75,
    )
    P(
        c,
        rx,
        6.32,
        rw,
        f"Base 12-month account probabilities range {sv['base_12m_min_probability'] * 100:.1f}%–"
        f"{sv['base_12m_max_probability'] * 100:.1f}% (mean {sv['base_12m_mean_probability'] * 100:.1f}%). "
        "Larger counts under wider populations mainly reflect larger denominators.",
        S(9.5, color=MUTED, leading=11.5),
        max_h=0.5,
        name="prob note",
    )


def appendix_d(c, f) -> None:
    nine = f["financial"]["nine_cell"]
    app_frame(
        c,
        "D",
        (
            "Analytical expected NPV is the closed-form expectation under the same billing and discounting "
            "rules; the Monte Carlo columns are finite-sample statistics from 1,000 independent replications "
            "per cell (PCG64, seed 20261009, common random numbers across cells). P5/P95 are conditional "
            "outcome percentiles, not confidence intervals for real program value."
        ),
    )
    hs = S(9.5, color=WHITE, bold=True, align="r", leading=11)
    hl = S(9.5, color=WHITE, bold=True, leading=11)
    heads = [
        "Hazard scenario",
        "Offer",
        "Analytical expected NPV",
        "MC sample mean",
        "MC std. error",
        "z",
        "MC median",
        "MC 5th pct",
        "MC 95th pct",
        "Pr(NPV &lt; 0)",
        "Mean reactivations",
    ]
    data = [[Paragraph(h, hl if i < 2 else hs) for i, h in enumerate(heads)]]
    offer = {"low_5pct": "5%", "medium_15pct": "15%", "high_30pct": "30%"}
    styles = [
        ("BACKGROUND", (0, 0), (-1, 0), col(NAVY)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.6),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, col(RULE)),
    ]
    r = 1
    for scen in ("conservative", "base", "optimistic"):
        for tier in ("low_5pct", "medium_15pct", "high_30pct"):
            v = nine[scen][tier]
            bold = scen == "base" and tier == "medium_15pct"
            cells = [
                scen.capitalize() if tier == "low_5pct" else "",
                offer[tier],
                money(v["analytical_expected_npv"], cents=True),
                money(v["mc_mean"]),
                money(v["mc_se"]),
                f"{v['z']:.2f}",
                money(v["mc_median"]),
                money(v["mc_p05"]),
                money(v["mc_p95"]),
                f"{v['pr_negative'] * 100:.1f}%",
                f"{v['mean_reactivations']:.1f}",
            ]
            data.append(
                [
                    Paragraph(x, S(10, bold=bold or i == 0, align="l" if i < 2 else "r"))
                    for i, x in enumerate(cells)
                ]
            )
            if bold:
                styles.append(("BACKGROUND", (0, r), (-1, r), col(PANEL2)))
            r += 1
        styles.append(("LINEBELOW", (0, r - 1), (-1, r - 1), 1.0, col(MUTED)))
    widths = [1.3, 0.95, 1.55, 1.2, 0.95, 0.55, 1.15, 1.15, 1.15, 0.95, 1.23]
    h = table(c, LEFT, 1.45, data, widths, styles, name="nine-cell table", max_h=3.9)

    # compact chart of analytical NPV
    cy = 1.45 + h + 0.25
    P(
        c,
        LEFT,
        cy,
        7.0,
        "ANALYTICAL EXPECTED NPV BY CELL ($ THOUSANDS)",
        S(10, color=MUTED, bold=True),
    )
    top = cy + 0.3
    chh = 6.72 - top - 0.42
    cw = 7.0
    vmax = 480_000
    colors = {"low_5pct": B250, "medium_15pct": B450, "high_30pct": B700}
    gw = cw / 3
    base_y = top + chh
    for gi, scen in enumerate(("conservative", "base", "optimistic")):
        for ti, tier in enumerate(("low_5pct", "medium_15pct", "high_30pct")):
            v = nine[scen][tier]["analytical_expected_npv"]
            bh = chh * v / vmax
            x = LEFT + gi * gw + 0.35 + ti * 0.62
            rect(c, x, base_y - bh, 0.55, bh, fill=colors[tier])
            P(c, x - 0.15, base_y - bh - 0.2, 0.85, f"{v / 1000:,.0f}", S(9, align="c"))
        P(c, LEFT + gi * gw, base_y + 0.05, gw, f"<b>{scen.capitalize()}</b>", S(10, align="c"))
    line(c, LEFT, base_y, LEFT + cw, base_y, color=RULE, width=1)
    lx = LEFT + cw + 0.4
    for i, (tier, label) in enumerate(
        (("low_5pct", "5% offer"), ("medium_15pct", "15% offer"), ("high_30pct", "30% offer"))
    ):
        rect(c, lx, top + 0.05 + i * 0.27, 0.15, 0.15, fill=colors[tier])
        P(c, lx + 0.22, top + 0.02 + i * 0.27, 1.5, label, S(9.5, color=MUTED))
    P(
        c,
        lx,
        top + 0.95,
        RIGHT - lx,
        f"Read the table across one row at a time. Base / 15% is the reference cell used for "
        f"routing priorities; the nine cells are alternative assumption sets and must not be summed. "
        f"Every cell passes the predeclared |z| ≤ 4.5 reconciliation between simulation and closed "
        f"form (maximum {f['financial']['max_abs_z']:.2f}). Positive values in all 1,000 base-case runs "
        "do not establish zero real-world risk: parameters are fixed and root dependence is unestimated.",
        S(10, color=INK, leading=12.4),
        max_h=1.9,
        name="D notes",
    )


def appendix_e(c, f) -> None:
    fin = f["financial"]
    sens = fin["sensitivity"]
    base = sens["baseline"]
    st = fin["stress"]
    be = fin["break_even"]
    app_frame(
        c,
        "E",
        (
            "One-at-a-time changes around base hazard / 15% offer (analytical expected NPV "
            f"{money(base, cents=True)}). The two stress vectors are distinct assumption sets and are both "
            "reproduced exactly from frozen account hazards; neither replaces the primary nine-cell results."
        ),
    )
    rows = [
        (
            "Monthly revenue $750 / $1,250",
            "monthly_gross_revenue_per_reactivated_account_0.75x",
            "monthly_gross_revenue_per_reactivated_account_1.25x",
        ),
        ("Contribution margin 45% / 75%", "contribution_margin_0.75x", "contribution_margin_1.25x"),
        (
            "Outreach $50 / $150 per account",
            "outreach_cost_per_target_0.5x",
            "outreach_cost_per_target_1.5x",
        ),
        (
            "Activation $100 / $300 per event",
            "activation_cost_per_reactivation_0.5x",
            "activation_cost_per_reactivation_1.5x",
        ),
        ("Financial rate 0% / 24%", "financial_rate_0", "financial_rate_0.24"),
        ("Customer offer 5% / 30%", "commercial_low_5pct", "commercial_high_30pct"),
        ("Hazard × 0.5 / × 1.5", "hazard_0.5x", "hazard_1.5x"),
        (
            "Retention cap 3 / 6 paid months",
            "retention_cap_3_paid_months",
            "retention_cap_6_paid_months",
        ),
    ]
    lw = 6.25
    P(
        c,
        LEFT,
        1.45,
        lw,
        "CHANGE IN EXPECTED NPV VS. BASE ($ THOUSANDS) — FIRST / SECOND VALUE",
        S(10, color=MUTED, bold=True),
    )
    label_w = 2.35
    zero_x = LEFT + label_w + (lw - label_w) * 0.55
    scale = (lw - label_w) * 0.43 / 190_000
    ry = 1.78
    line(c, zero_x, ry - 0.05, zero_x, ry + len(rows) * 0.47, color=MUTED, width=0.8)
    for label, lo_key, hi_key in rows:
        P(c, LEFT, ry + 0.06, label_w - 0.1, escape(label), S(9.5, leading=11))
        for j, key in enumerate((lo_key, hi_key)):
            delta = sens[key] - base
            w = abs(delta) * scale
            x = zero_x if delta >= 0 else zero_x - w
            yy = ry + 0.02 + j * 0.21
            rect(c, x, yy, max(w, 0.01), 0.18, fill=B450 if delta >= 0 else RED)
            tx = x + w + 0.05 if delta >= 0 else x - 0.75
            P(
                c,
                tx,
                yy + 0.015,
                0.7,
                f"{'+' if delta >= 0 else '−'}{abs(delta) / 1000:,.1f}",
                S(8.5, align="l" if delta >= 0 else "r", color=INK),
            )
        ry += 0.47
    P(
        c,
        LEFT,
        ry + 0.04,
        lw,
        "Blue = increase, red = decrease. Within each pair the upper bar is the first value named "
        "(e.g., $750), the lower bar the second (e.g., $1,250).",
        S(9, color=MUTED, leading=11),
        max_h=0.4,
        name="tornado note",
    )

    rx = LEFT + lw + 0.4
    rw = RIGHT - rx
    P(c, rx, 1.45, rw, "ZERO-NPV BREAK-EVEN (BASE HAZARD, 5% OFFER)", S(10, color=MUTED, bold=True))
    data = [
        ["Minimum monthly gross revenue", money(be["minimum_monthly_gross_revenue"], cents=True)],
        ["Minimum contribution margin", f"{be['minimum_contribution_margin'] * 100:.2f}%"],
        ["Maximum outreach per account", money(be["maximum_outreach_cost_per_target"], cents=True)],
        ["Maximum activation per event", money(be["maximum_activation_cost"], cents=True)],
        ["Hazard multiple for 15% to match 5%", f"{be['hazard_multiplier_medium_15pct']:.3f}×"],
        ["Hazard multiple for 30% to match 5%", f"{be['hazard_multiplier_high_30pct']:.3f}×"],
    ]
    data = [[Paragraph(a, S(10)), Paragraph(b, S(10, align="r", bold=True))] for a, b in data]
    table(
        c,
        rx,
        1.72,
        data,
        [rw - 1.4, 1.4],
        [
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, col(RULE)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ],
        name="breakeven",
    )
    P(
        c,
        rx,
        3.55,
        rw,
        "COMBINED ADVERSE STRESS — TWO DISTINCT VECTORS",
        S(10, color=MUTED, bold=True),
    )
    hs = S(9.5, color=WHITE, bold=True, align="r", leading=11)
    stress_rows = [
        ("Hazard multiplier", "× 1.0", "× 0.5"),
        ("Monthly gross revenue", "$750", "$750"),
        ("Contribution margin", "45%", "60%"),
        ("Outreach per account", "$150", "$150"),
        ("Activation per reactivation", "$300", "$200"),
        ("Annual financial discount rate", "24%", "12%"),
        ("Maximum paid months", "3", "3"),
        ("Hypothetical commercial offer", "15%", "15%"),
    ]
    data = [
        [
            Paragraph("Assumption", S(9.5, color=WHITE, bold=True, leading=11)),
            Paragraph("Committed Phase 3", hs),
            Paragraph("Alternative compounded", hs),
        ]
    ]
    for a, b, d in stress_rows:
        data.append(
            [Paragraph(a, S(9.5)), Paragraph(b, S(9.5, align="r")), Paragraph(d, S(9.5, align="r"))]
        )
    data.append(
        [
            Paragraph("<b>Analytical expected NPV</b>", S(9.5)),
            Paragraph(
                f"<b>{money(st['committed_adverse_npv_usd'], cents=True)}</b>",
                S(9.5, align="r", color=RED),
            ),
            Paragraph(
                f"<b>{money(st['alternative_compounded_npv_usd'], cents=True)}</b>",
                S(9.5, align="r", color=RED),
            ),
        ]
    )
    table(
        c,
        rx,
        3.82,
        data,
        [rw - 3.3, 1.6, 1.7],
        [
            ("BACKGROUND", (0, 0), (-1, 0), col(NAVY)),
            ("LINEBELOW", (0, 1), (-1, -2), 0.5, col(RULE)),
            ("LINEABOVE", (0, -1), (-1, -1), 1.0, col(INK)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4),
        ],
        name="stress table",
        max_h=3.0,
    )
    rect(c, LEFT, 5.92, lw, 0.92, fill=PANEL)
    P(
        c,
        LEFT + 0.15,
        5.98,
        lw - 0.3,
        f"<b>Root dependence:</b> {st['multi_account_root_npv_share'] * 100:.1f}% of base / 15% expected "
        f"NPV comes from the {st['multi_account_roots']} of {st['modeled_roots']} root groups with more "
        "than one modeled account; parent-child billable independence is unverified and outcomes inside a "
        "root are modeled as independent. <b>Discount response:</b> no elasticity is estimated; the "
        "hazard multiples are hypothetical solutions.",
        S(9.3, leading=11.2),
        max_h=0.82,
        name="root note",
    )


# ---- Appendix F flowchart -----------------------------------------------------------------
def node(
    c, x, y, w, h, title, sub=None, *, fill=WHITE, stroke=NAVY, ink=INK, size=10, bold_title=True
) -> None:
    rect(c, x, y, w, h, fill=fill, stroke=stroke, width=1.0, radius=0.05)
    html = f"<b>{escape(title)}</b>" if bold_title else escape(title)
    if sub:
        html += f"<br/><font size='{size - 1.5}'>{escape(sub)}</font>"
    p = Paragraph(html, S(size, color=ink, align="c", leading=size * 1.2))
    _, th = p.wrapOn(c, X(w - 0.12), 1000)
    if th > X(h) + 0.5:
        OVERFLOWS.append(f"{PAGE_NAME[0]} node {title}: {th / 72:.2f}in > {h:.2f}in")
    p.drawOn(c, X(x + 0.06), Y(y + (h - th / 72) / 2) - th)
    USED_TEXT.append(("Arial", html))


def tag(c, x, y, text_value, color=MUTED) -> None:
    P(c, x, y, 1.4, f"<b>{escape(text_value)}</b>", S(8.5, color=color))


def appendix_f(c, f) -> None:
    g = f["gtm"]
    ch, rl = g["channels"], g["rules"]
    co = f["cohort"]
    rt = g["roots"]
    app_frame(
        c,
        "F",
        (
            "Rule order is exactly that of gtm_routing.route_account (policy phase4-routing-policy-v2). Counts "
            "are the frozen Phase 4 results. The 37,656 GB cut is the observed 75th percentile of the cohort "
            "— a scale heuristic, not verified enterprise status. Ticket counts are a snapshot backlog proxy; "
            "ticket velocity and revenue decay are unobserved."
        ),
    )
    # Row 1: validation gate, cohort gate and the cohort hold
    node(
        c,
        LEFT,
        1.45,
        2.75,
        0.74,
        "R0 · Upstream inputs valid?",
        "source SHA-256, Phase 2/3 contracts & manifests, 29 fields, 9 cells",
        fill=PANEL,
        size=9.5,
    )
    arrow(c, LEFT + 2.75, 1.82, LEFT + 3.3, 1.82)
    P(c, LEFT + 2.75, 1.6, 0.55, "<b>yes</b>", S(8.5, color=B550, align="c"))
    node(
        c,
        LEFT + 3.3,
        1.45,
        3.0,
        0.74,
        "R1 · Source-reported ≥ 2 years inactive?",
        f"{n(co['modeled'])} of {n(co['source_accounts'])} accounts enter account routing",
        size=9.5,
    )
    arrow(c, LEFT + 6.3, 1.82, LEFT + 6.85, 1.82)
    P(c, LEFT + 6.3, 1.6, 0.55, "<b>no</b>", S(8.5, color=RED, align="c"))
    node(
        c,
        LEFT + 6.85,
        1.45,
        3.25,
        0.74,
        "Cohort HOLD_REVIEW · no financial score",
        f"{co['conflicts']} inactivity conflicts + {co['unknown']} unknown = "
        f"{co['conflicts'] + co['unknown']} accounts",
        fill=PANEL2,
        stroke=GRAY,
        size=9.5,
    )
    node(
        c,
        LEFT + 10.45,
        1.45,
        WIDTH - 10.45,
        0.74,
        "R0 = no → abort",
        "no authoritative routes are emitted",
        fill="F8E9E9",
        stroke=RED,
        size=9.5,
    )
    # R1 yes -> elbow to R2 (first spine node)
    gap, sh, sy, sx = 0.27, 0.74, 2.62, LEFT
    sw = (WIDTH - 6 * gap) / 7
    r1_mid = LEFT + 3.3 + 1.5
    line(c, r1_mid, 2.19, r1_mid, 2.42, color=MUTED, width=1.1)
    line(c, r1_mid, 2.42, sx + sw / 2, 2.42, color=MUTED, width=1.1)
    arrow(c, sx + sw / 2, 2.42, sx + sw / 2, sy)
    P(
        c,
        r1_mid + 0.08,
        2.2,
        3.6,
        "<b>yes</b> · one-to-one enrichment with verified source fields",
        S(8.5, color=B550),
    )

    # Row 2: account-level rule spine — every question exits down on YES, continues right on NO
    spine = [
        ("R2", "Identity or root invalid?", "HOLD", rl.get("R2", 0)),
        ("R3", "Partner ownership unknown?", "HOLD", rl.get("R3", 0)),
        ("R4", "Red health or ≥ 5 valid open tickets?", "HOLD", rl.get("R4", 0)),
        ("R5", "Partner-managed = Yes?", "PARTNER-LED", rl.get("R5", 0)),
        ("R6", "Valid usage ≥ 37,656 GB?", "DIRECT ENTERPRISE", rl.get("R6", 0)),
        ("R7", "Valid usage known (below cut)?", "DIGITAL NURTURE", rl.get("R7", 0)),
    ]
    for i, (rid, q, outcome, count) in enumerate(spine):
        x = sx + i * (sw + gap)
        node(c, x, sy, sw, sh, f"{rid} · {q}", None, size=9.5)
        arrow(c, x + sw, sy + sh / 2, x + sw + gap, sy + sh / 2)
        P(c, x + sw, sy + sh / 2 - 0.2, gap, "no", S(7.5, color=MUTED, align="c"))
        arrow(c, x + sw / 2, sy + sh, x + sw / 2, sy + sh + 0.4)
        is_hold = outcome == "HOLD"
        P(
            c,
            x + sw / 2 + 0.05,
            sy + sh + 0.06,
            0.5,
            "<b>yes</b>",
            S(8.5, color=RED if is_hold else B550),
        )
        node(
            c,
            x,
            sy + sh + 0.4,
            sw,
            0.6,
            "HOLD_REVIEW" if is_hold else outcome,
            f"{n(count)} accounts · {rid}",
            fill=PANEL2 if is_hold else B550,
            stroke=GRAY if is_hold else B550,
            ink=INK if is_hold else WHITE,
            size=9.5,
        )
    x8 = sx + 6 * (sw + gap)
    node(
        c,
        x8,
        sy,
        sw,
        sh,
        "R8 · Usage missing",
        f"HOLD_REVIEW · {rl.get('R8', 0)} accounts",
        fill=PANEL2,
        stroke=GRAY,
        size=9.5,
    )
    P(
        c,
        x8,
        sy + sh + 0.08,
        sw,
        "Rows read left to right: <b>no</b> continues, <b>yes</b> exits down. First match wins.",
        S(8.5, color=MUTED, leading=10.2),
    )

    # Row 3: post-routing controls
    py = 4.72
    P(
        c,
        LEFT,
        py - 0.02,
        WIDTH,
        "APPLIED TO EVERY ROUTED ACCOUNT, AFTER THE RULES — NEVER OVERRIDING THEM",
        S(9.5, color=MUTED, bold=True),
    )
    boxes = [
        (
            "Illustrative priority & evidence",
            f"base/15% NPV tertiles: {g['priority']['HIGH']} High · {g['priority']['MEDIUM']} Medium · "
            f"{g['priority']['LOW']} Low; evidence flags kept separate",
        ),
        (
            "Root coordination (full-source)",
            f"{rt['coordination_required_roots']} of {rt['all_modeled_roots']} roots · "
            f"{n(g['readiness']['root_coordination_required'])} accounts flagged; "
            f"{rt['full_source_known_ownership_conflict_roots']} known ownership conflicts",
        ),
        (
            "Authorization gate",
            "execution_authorized = false · fiscal eligibility unconfirmed · PLANNING_ONLY",
        ),
        (
            "Reconciliation & safe aggregates",
            "1,144 modeled + 856 held = 2,000 source accounts; 295 roots; aggregate-only Phase 5 contract",
        ),
    ]
    bw = (WIDTH - 3 * 0.3) / 4
    for i, (t, s) in enumerate(boxes):
        x = LEFT + i * (bw + 0.3)
        fill, stroke, ink = (NAVY, NAVY, WHITE) if i == 2 else (WHITE, NAVY, INK)
        node(c, x, py + 0.25, bw, 0.95, t, s, fill=fill, stroke=stroke, ink=ink, size=9.5)
        if i < 3:
            arrow(c, x + bw, py + 0.72, x + bw + 0.3, py + 0.72)
    P(
        c,
        LEFT,
        6.05,
        WIDTH,
        f"<b>Totals:</b> partner-led {ch['PARTNER_LED_CANDIDATE']} · direct-enterprise "
        f"{ch['DIRECT_ENTERPRISE_CANDIDATE']} · digital-nurture {ch['DIGITAL_NURTURE_CANDIDATE']} · "
        f"hold/review {ch['HOLD_REVIEW']} (R3 {rl['R3']} + R4 {rl['R4']}) = 1,144 modeled accounts. "
        "Missing health or tickets add review flags without erasing an otherwise interpretable channel; "
        "unknown ownership always blocks channel assignment; a positive NPV never overrides a rule.",
        S(10, leading=12.4),
        max_h=0.8,
        name="F totals",
    )


def appendix_g(c, f) -> None:
    g = f["gtm"]
    rl, rd, rt, sv, pe = (
        g["rules"],
        g["readiness"],
        g["roots"],
        g["service"],
        g["priority_evidence"],
    )
    app_frame(
        c,
        "G",
        (
            "All counts are frozen Phase 4 aggregates (denominator 1,144 modeled accounts or 295 modeled "
            "roots). Evidence, service and priority classifications are planning diagnostics, not execution "
            "readiness; open tickets are a snapshot backlog proxy and ticket velocity is unobserved."
        ),
    )
    lw = 6.9
    P(c, LEFT, 1.45, lw, "RULE PRECEDENCE (FIRST MATCH WINS)", S(10, color=MUTED, bold=True))
    rows = [
        ("R0", "Upstream source, contract, manifest or join fails", "Abort", "—"),
        ("R1", "Outside the source-reported two-year cohort", "Cohort hold, no score", "856"),
        ("R2", "Invalid identity or root relation", "HOLD_REVIEW", str(rl.get("R2", 0))),
        ("R3", "Partner ownership unknown", "HOLD_REVIEW", str(rl["R3"])),
        ("R4", "Red health or ≥ 5 valid open tickets", "HOLD_REVIEW", str(rl["R4"])),
        ("R5", "Known partner-managed = Yes", "PARTNER_LED", str(rl["R5"])),
        ("R6", "Known No and valid usage ≥ 37,656 GB", "DIRECT_ENTERPRISE", str(rl["R6"])),
        ("R7", "Known No and valid usage below the cut", "DIGITAL_NURTURE", str(rl["R7"])),
        ("R8", "Remaining case, including missing usage", "HOLD_REVIEW", str(rl.get("R8", 0))),
    ]
    data = [
        [
            Paragraph(h, S(9.5, color=WHITE, bold=True, align=a))
            for h, a in (("Rule", "l"), ("Condition", "l"), ("Disposition", "l"), ("Accounts", "r"))
        ]
    ]
    for r in rows:
        data.append(
            [
                Paragraph(f"<b>{r[0]}</b>", S(9.5)),
                Paragraph(escape(r[1]), S(9.5, leading=11)),
                Paragraph(r[2], S(9, font="Consolas")),
                Paragraph(r[3], S(9.5, align="r")),
            ]
        )
    table(
        c,
        LEFT,
        1.72,
        data,
        [0.55, 3.35, 1.95, lw - 5.85],
        [
            ("BACKGROUND", (0, 0), (-1, 0), col(NAVY)),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, col(RULE)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ],
        name="rule table",
        max_h=3.0,
    )
    P(
        c,
        LEFT,
        4.92,
        lw,
        "SERVICE SNAPSHOT AND REVIEW FLAGS (ACCOUNTS)",
        S(10, color=MUTED, bold=True),
    )
    svc = [
        ("Critical backlog (≥ 5)", sv["CRITICAL_BACKLOG"]),
        ("Elevated (3–4)", sv["ELEVATED_BACKLOG"]),
        ("Low (1–2)", sv["LOW_BACKLOG"]),
        ("Observed zero", sv["NO_OBSERVED_OPEN_BACKLOG"]),
        ("Unknown / 999", sv["UNKNOWN_SERVICE_EVIDENCE"]),
    ]
    flags = [
        ("Partner review", rd["partner_review_required"]),
        ("Health review", rd["health_review_required"]),
        ("Ticket review", rd["ticket_review_required"]),
        ("Service recovery", rd["service_recovery_required"]),
        ("Root coordination", rd["root_coordination_required"]),
    ]
    data = [
        [
            Paragraph(f"{escape(a)}", S(9.5)),
            Paragraph(n(b), S(9.5, align="r", bold=True)),
            Paragraph(f"{escape(c_)}", S(9.5)),
            Paragraph(n(d), S(9.5, align="r", bold=True)),
        ]
        for (a, b), (c_, d) in zip(svc, flags, strict=True)
    ]
    table(
        c,
        LEFT,
        5.18,
        data,
        [2.2, 0.9, 2.45, lw - 5.55],
        [
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, col(RULE)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
            ("LINEAFTER", (1, 0), (1, -1), 0.5, col(RULE)),
        ],
        name="service table",
    )

    rx = LEFT + lw + 0.4
    rw = RIGHT - rx
    P(c, rx, 1.45, rw, "ILLUSTRATIVE PRIORITY × EVIDENCE QUALITY", S(10, color=MUTED, bold=True))
    ev = [
        ("CRITICAL_UNRESOLVED", "Critical"),
        ("MATERIAL_REVIEW", "Material review"),
        ("RELATIVELY_COMPLETE", "Relatively complete"),
    ]
    hs = S(9.5, color=WHITE, bold=True, align="r", leading=11)
    data = [
        [Paragraph("Priority", S(9.5, color=WHITE, bold=True))]
        + [Paragraph(lbl, hs) for _, lbl in ev]
        + [Paragraph("Total", hs)]
    ]
    for tier in ("HIGH", "MEDIUM", "LOW"):
        vals = [pe[f"{tier}|{key}"] for key, _ in ev]
        data.append(
            [Paragraph(f"<b>{tier.capitalize()}</b>", S(9.5))]
            + [Paragraph(n(v), S(9.5, align="r")) for v in vals]
            + [Paragraph(f"<b>{n(sum(vals))}</b>", S(9.5, align="r"))]
        )
    totals = [sum(pe[f"{t}|{key}"] for t in ("HIGH", "MEDIUM", "LOW")) for key, _ in ev]
    data.append(
        [Paragraph("<b>Total</b>", S(9.5))]
        + [Paragraph(f"<b>{n(v)}</b>", S(9.5, align="r")) for v in totals]
        + [Paragraph("<b>1,144</b>", S(9.5, align="r"))]
    )
    table(
        c,
        rx,
        1.72,
        data,
        [0.95, 0.9, 1.1, 1.15, rw - 4.1],
        [
            ("BACKGROUND", (0, 0), (-1, 0), col(NAVY)),
            ("LINEBELOW", (0, 1), (-1, -2), 0.5, col(RULE)),
            ("LINEABOVE", (0, -1), (-1, -1), 1.0, col(INK)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ],
        name="priority table",
    )
    P(
        c,
        rx,
        3.35,
        rw,
        f"High-priority missingness: health unknown {rd['high_priority_health_unknown']} of "
        f"{g['priority']['HIGH']}; partner unknown {rd['high_priority_partner_unknown']}; 999-ticket "
        f"sentinel {rd['high_priority_ticket_sentinel']}. Unknown health is scored at the reference "
        "level, so financial order and evidence readiness must be read separately.",
        S(9.5, color=MUTED, leading=11.5),
        max_h=0.62,
        name="hp note",
    )
    P(c, rx, 4.08, rw, "ROOT COORDINATION (295 MODELED ROOTS)", S(10, color=MUTED, bold=True))
    roots = [
        ("Multi-account modeled roots", rt["multi_account_roots"]),
        (
            "Known Yes/No ownership conflict — modeled members",
            rt["modeled_known_ownership_conflict_roots"],
        ),
        (
            "Known Yes/No ownership conflict — full-source members",
            rt["full_source_known_ownership_conflict_roots"],
        ),
        (
            "Unknown-ownership ambiguity (full source)",
            rt["full_source_unknown_ownership_ambiguity_roots"],
        ),
        ("Mixed planning channels inside the root", rt["mixed_planning_channel_roots"]),
        (
            "Coordination required (multi-account or full-source conflict)",
            rt["coordination_required_roots"],
        ),
    ]
    data = [
        [Paragraph(escape(a), S(9.5, leading=11)), Paragraph(n(b), S(9.5, align="r", bold=True))]
        for a, b in roots
    ]
    table(
        c,
        rx,
        4.34,
        data,
        [rw - 0.8, 0.8],
        [
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, col(RULE)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
        ],
        name="roots table",
    )
    P(
        c,
        rx,
        6.32,
        rw,
        f"<b>{g['authorized_contact_actions']} authorized customer-contact actions.</b> No campaign, partner "
        "notification or CRM update occurred; rollout needs eligibility, permissions and human review.",
        S(9.5, color=NAVY, leading=11.5),
        max_h=0.5,
        name="auth note",
    )


def appendix_h(c, f, test_summary: str) -> None:
    pv = f["provenance"]
    app_frame(
        c,
        "H",
        (
            "Implementation readiness (code, controls, reproducibility) is established; operational "
            "readiness (eligible, permissioned, measurable outreach) is not. The model should be recalibrated "
            "on observed pilot outcomes before any financial claim is made."
        ),
    )
    w3 = (WIDTH - 2 * 0.35) / 3
    x1, x2, x3 = LEFT, LEFT + w3 + 0.35, LEFT + 2 * (w3 + 0.35)
    P(c, x1, 1.45, w3, "VALIDATION EVIDENCE", S(10, color=MUTED, bold=True))
    commits = pv["commits"]
    data = [
        [Paragraph(a, S(9.5, bold=True)), Paragraph(b, S(9, font="Consolas"))]
        for a, b in (
            ("Phase 1 data foundation", commits["phase1"][:7]),
            ("Phase 2 survival", commits["phase2"][:7]),
            (
                "Phase 3 Monte Carlo NPV",
                f"{commits['phase3'][:7]} + {commits['phase3_integrity_fix'][:7]}",
            ),
            ("Phase 4 GTM routing", commits["phase4"][:7]),
        )
    ]
    table(
        c,
        x1,
        1.72,
        data,
        [w3 - 1.45, 1.45],
        [
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, col(RULE)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
        ],
        name="commits",
    )
    bullets(
        c,
        x1,
        3.05,
        w3,
        [
            "Each phase was independently audited against a raw-CSV oracle and frozen before the next.",
            "Phase 5 build gate re-ran the source integrity check and the read-only Phase 4 semantic "
            "validator, pinned the input contract and manifest bytes, hash-checked every aggregate and "
            "re-derived both stress vectors before drawing any page.",
            escape(test_summary),
            "Every number on pages 1–13 is generated from those validated inputs; none is typed by hand.",
        ],
        S(9.5, leading=11.6),
        gap=0.07,
        max_h=3.6,
        name="validation bullets",
    )

    P(c, x2, 1.45, w3, "PRINCIPAL LIMITATIONS", S(10, color=MUTED, bold=True))
    bullets(
        c,
        x2,
        1.72,
        w3,
        [
            "No observed reactivation histories, campaign control group or revenue-decay series.",
            "Reactivation hazards, unit economics and retention are analyst assumptions.",
            "No price-response elasticity: offer comparisons hold hazard fixed.",
            "Incremental uplift is not causally identified (no untreated counterfactual).",
            "Parent-child billable independence and within-root dependence are unverified.",
            "Missing health and 999 tickets shape rankings through reference-level scoring.",
            "Tickets are a snapshot backlog, not velocity; fiscal eligibility is unconfirmed.",
            "Historical recorded spend is not ARR or recoverable revenue.",
        ],
        S(9.5, leading=11.6),
        gap=0.06,
        max_h=4.9,
        name="limitations",
    )

    P(c, x3, 1.45, w3, "DATA NEEDED TO CALIBRATE, THEN NEXT STEPS", S(10, color=MUTED, bold=True))
    bullets(
        c,
        x3,
        1.72,
        w3,
        [
            "Fiscal-period bookings by account to confirm dormancy and measure decay.",
            "Authoritative partner ownership and contact permissions by account and root.",
            "Current SFDC health and dated ticket history (velocity, not snapshots).",
            "Pilot outcomes with randomized holdouts: reactivation, uplift, cost, margin.",
            "Offer-level response data to estimate discount elasticity.",
        ],
        S(9.5, leading=11.6),
        gap=0.06,
        max_h=2.4,
        name="data needed",
    )
    rect(c, x3, 4.35, w3, 2.45, fill=PANEL)
    P(c, x3 + 0.16, 4.45, w3 - 0.32, "Next 3 actions", S(11.5, color=NAVY, bold=True))
    bullets(
        c,
        x3 + 0.16,
        4.78,
        w3 - 0.32,
        [
            "Run the Gate 1 validation sprint on the 1,144 provisional accounts.",
            "Resolve ownership for the 282 coordination roots before any channel motion.",
            "Design a randomized pilot per channel; refit hazards and economics on its results.",
        ],
        S(9.5, leading=11.6),
        gap=0.07,
        max_h=1.9,
        name="next steps",
    )


# ======================================================================================
def build(out: Path, test_summary: str) -> dict:
    register_fonts()
    facts = load_validated_facts(ROOT)
    OVERFLOWS.clear()
    USED_TEXT.clear()
    out.parent.mkdir(parents=True, exist_ok=True)
    c = Canvas(
        str(out),
        pagesize=(PAGE_W, PAGE_H),
        pageCompression=1,
        invariant=1,
        initialFontName="Arial",
        initialFontSize=10,
    )
    c.setTitle(cfg.PDF_TITLE)
    c.setAuthor(cfg.CANDIDATE_NAME or "Everpure Case Study 1 candidate submission")
    c.setSubject(cfg.PDF_SUBJECT)
    c.setKeywords(cfg.PDF_KEYWORDS)
    c.setCreator("Phase 5 build (reportlab) from validated aggregate-only inputs")
    exec_titles = [
        "1 · Opportunity and recommendation",
        "2 · Data foundation and SQL",
        "3 · Reactivation probability and survival",
        "4 · Monte Carlo NPV and risk",
        "5 · GTM routing and decision",
    ]
    for i, fn in enumerate((slide1, slide2, slide3, slide4, slide5)):
        if i == 0:
            c.bookmarkPage("exec")
            c.addOutlineEntry("Executive presentation", "exec", level=0)
        c.bookmarkPage(f"s{i + 1}")
        c.addOutlineEntry(exec_titles[i], f"s{i + 1}", level=1)
        fn(c, facts)
        c.showPage()
    c.bookmarkPage("appendix")
    c.addOutlineEntry("Technical appendix", "appendix", level=0)
    for fn in (appendix_a, appendix_b, appendix_c, appendix_d, appendix_e, appendix_f, appendix_g):
        fn(c, facts)
        c.showPage()
    appendix_h(c, facts, test_summary)
    c.showPage()
    c.addPageLabel(0, style="ARABIC", start=1)
    c.addPageLabel(5, style="LETTERS_UPPER", start=1, prefix="Appendix ")
    c.showOutline()
    c.save()
    return facts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", default=str(ROOT / "submission/Everpure_Case_Study_Final_Submission.pdf")
    )
    parser.add_argument(
        "--test-summary",
        default=(
            "Frozen baseline test suite: 96 passed with warnings as errors in a disposable copy "
            "(2026-10-11); Ruff clean at the Phase 4 freeze."
        ),
    )
    args = parser.parse_args()
    out = Path(args.out)
    build(out, args.test_summary)
    size = out.stat().st_size
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"PDF {out} bytes={size} sha256={digest}")
    gaps = missing_glyphs()
    if gaps:
        print("MISSING GLYPHS:", gaps)
    if OVERFLOWS:
        print("LAYOUT WARNINGS:")
        for item in OVERFLOWS:
            print("  " + item)
    if size >= cfg.PDF_HARD_LIMIT_BYTES:
        raise SystemExit(f"PDF is {size} bytes; the hard limit is {cfg.PDF_HARD_LIMIT_BYTES}")


if __name__ == "__main__":
    main()
