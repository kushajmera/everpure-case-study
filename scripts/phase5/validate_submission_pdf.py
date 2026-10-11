"""Release gate for the consolidated submission PDF: size, structure, numbers, links, safety."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import submission_config as cfg  # noqa: E402
from phase5_inputs import ROOT  # noqa: E402

REQUIRED_TEXT = {
    # source and cohort
    "source accounts": ["2,000", "1,144", "57.2%", "562", "294", "295", "301", "1,699", "4,889"],
    # survival
    "survival": ["66.3", "128.7", "206.2", "66.33", "128.72", "206.21", "121.1", "112.4"],
    # financial
    "nine-cell": [
        "$66,866.14",
        "$46,464.54",
        "$15,862.13",
        "$241,533.35",
        "$201,501.66",
        "$141,454.13",
        "$464,630.73",
        "$399,568.03",
        "$301,973.98",
    ],
    "monte carlo": [
        "$202.9k",
        "$202.6k",
        "$150.7k",
        "$256.5k",
        "$202,912",
        "$202,618",
        "$150,709",
        "$256,482",
        "0 of 1,000",
    ],
    "assumptions": ["$1,000", "60%", "$100", "$200", "12%", "12 months"],
    "stress": ["−$124,647.43", "−$124,704.05", "−$124.6k"],
    "gtm": [
        "247",
        "21.6%",
        "66",
        "5.8%",
        "205",
        "17.9%",
        "626",
        "54.7%",
        "288",
        "418",
        "438",
        "187 of 288",
        "235 of 295 roots",
        "282 roots",
        "1,131",
        "518",
    ],
    "authorization": ["authorized customer-contact actions", "execution_authorized = false"],
    "caveats": [
        "not verified profit",
        "not causal",
        "fiscal-year eligibility",
        "not observed conversions",
        "assumption-based",
        "synthetic",
    ],
}
# Generic patterns are written so they never match their own source text; the local account
# name is derived at runtime so it is never stored in a published file.
FORBIDDEN = [
    r"ACC_\d+",
    r"[A-Za-z]:\\\\Users",
    r"[/]Users[/]",
    r"local[_]only/",
    re.escape(Path.home().name),
]


def validate(pdf_path: Path) -> dict:
    data = pdf_path.read_bytes()
    size = pdf_path.stat().st_size
    doc = pymupdf.open(pdf_path)
    pages = [doc[i].get_text() for i in range(doc.page_count)]
    text_all = " ".join(" ".join(pages).split())
    text_folded = text_all.casefold()
    labels = [doc[i].get_label() for i in range(doc.page_count)]
    links = [
        sorted({link.get("uri") for link in doc[i].get_links() if link.get("uri")})
        for i in range(doc.page_count)
    ]
    images = sum(len(doc[i].get_images(full=True)) for i in range(doc.page_count))
    fonts = sorted({f[3] for i in range(doc.page_count) for f in doc.get_page_fonts(i)})
    rendered_fonts = sorted(
        {
            span["font"]
            for i in range(doc.page_count)
            for block in doc[i].get_text("dict")["blocks"]
            for line_ in block.get("lines", [])
            for span in line_["spans"]
            if span["text"].strip()
        }
    )
    embedded = {
        f[3]: bool(f[1] in ("ttf", "cff", "otf") and "+" in f[3])
        for i in range(doc.page_count)
        for f in doc.get_page_fonts(i)
    }
    checks: dict[str, object] = {}
    checks["bytes_below_hard_limit"] = size < cfg.PDF_HARD_LIMIT_BYTES
    checks["bytes_at_or_below_target"] = size <= cfg.PDF_TARGET_BYTES
    checks["page_count_13"] = doc.page_count == 13
    checks["executive_pages_first_five"] = labels[:5] == ["1", "2", "3", "4", "5"] and all(
        f"Executive slide {i + 1} of 5" in pages[i] for i in range(5)
    )
    checks["appendix_pages_labeled"] = labels[5:] == [f"Appendix {c}" for c in "ABCDEFGH"] and all(
        f"Appendix {c} —" in pages[5 + i] for i, c in enumerate("ABCDEFGH")
    )
    checks["no_executive_label_after_page_5"] = not any(
        "Executive slide" in page for page in pages[5:]
    )
    missing = {
        group: [value for value in values if value.casefold() not in text_folded]
        for group, values in REQUIRED_TEXT.items()
    }
    checks["required_values_present"] = not any(missing.values())
    expected_links = {cfg.DRIVE_URL, cfg.GITHUB_URL}
    checks["slide5_links_exact"] = set(links[4]) == expected_links
    checks["appendixA_links_exact"] = set(links[5]) == expected_links
    checks["drive_label_on_slide5_and_appendixA"] = cfg.DRIVE_LABEL in pages[4].replace(
        "\n", " "
    ) and cfg.DRIVE_LABEL in pages[5].replace("\n", " ")
    checks["no_unexpected_links"] = all(set(page_links) <= expected_links for page_links in links)
    checks["vector_only_no_raster_images"] = images == 0
    checks["text_searchable_every_page"] = all(len(page.strip()) > 200 for page in pages)
    forbidden_hits = {pattern: len(re.findall(pattern, text_all)) for pattern in FORBIDDEN}
    raw_hits = {pattern: len(re.findall(pattern.encode(), data)) for pattern in FORBIDDEN}
    checks["no_identifiers_or_local_paths"] = not any(forbidden_hits.values()) and not any(
        raw_hits.values()
    )
    meta = doc.metadata
    checks["metadata_title_set"] = meta.get("title") == cfg.PDF_TITLE
    checks["not_encrypted"] = not doc.is_encrypted
    checks["rendered_fonts_embedded_subsets"] = bool(rendered_fonts) and all(
        any(name.endswith(font) and ok for name, ok in embedded.items()) for font in rendered_fonts
    )
    result = {
        "path": pdf_path.relative_to(ROOT).as_posix(),
        "bytes": size,
        "sha256": hashlib.sha256(data).hexdigest(),
        "pages": doc.page_count,
        "page_labels": labels,
        "links_by_page": {
            str(i + 1): page_links for i, page_links in enumerate(links) if page_links
        },
        "raster_images": images,
        "fonts_referenced": fonts,
        "fonts_rendering_text": rendered_fonts,
        "metadata": {k: v for k, v in meta.items() if v},
        "missing_required_values": {k: v for k, v in missing.items() if v},
        "forbidden_pattern_hits": forbidden_hits,
        "checks": checks,
        "passed": all(bool(v) for v in checks.values()),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf", default=str(ROOT / "submission/Everpure_Case_Study_Final_Submission.pdf")
    )
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()
    result = validate(Path(args.pdf))
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.json_out:
        Path(args.json_out).write_text(text + "\n", encoding="utf-8")
    print(text)
    if not result["passed"]:
        raise SystemExit("PDF release gate FAILED")


if __name__ == "__main__":
    main()
