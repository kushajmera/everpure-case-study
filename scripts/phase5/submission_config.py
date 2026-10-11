"""Single place for Phase 5 delivery settings that may change without touching any analysis.

Changing a link here and re-running ``build_submission.py`` regenerates the deck, the
consolidated PDF, the evidence index and the manifests; no financial or routing value
is recomputed or altered by a link change.
"""

GITHUB_URL = "https://github.com/kushajmera/everpure-case-study"
GITHUB_REMOTE = "https://github.com/kushajmera/everpure-case-study.git"
DRIVE_URL = "https://drive.google.com/drive/folders/1Ixur5zMZVuDybzTabTmsl3SsbrRX-Xts?usp=sharing"

DRIVE_LABEL = "Full Analytical Evidence & Diagrams — Google Drive"
GITHUB_LABEL = "Executable Code, SQL & Notebooks — GitHub"

# Optional; left blank so no candidate identity is invented. When set, it appears in the
# slide footer and PDF author metadata.
CANDIDATE_NAME = ""

DECK_TITLE = "Everpure — Reactivating Long-Dormant Accounts"
PDF_TITLE = "Everpure Case Study 1 — Install Base Monetization: Final Submission"
PDF_SUBJECT = (
    "Five-slide executive presentation with technical appendix: data foundation, "
    "survival analysis, Monte Carlo NPV and GTM routing"
)
PDF_KEYWORDS = (
    "Everpure; install base; reactivation; survival analysis; Monte Carlo NPV; GTM routing"
)

PDF_HARD_LIMIT_BYTES = 1_000_000
PDF_TARGET_BYTES = 850_000
