# SYNTHETIC METHODOLOGY DEMONSTRATION — NOT OBSERVED EVERPURE REVENUE

These five invented account IDs and four invented fiscal periods exist solely to test and explain longitudinal SQL. They are never joined to `data/raw/Case_Study_1_Install_Base_Reactivation.csv` or included in Phase 1 financial totals. In this fixture, each root account's own period revenue is independent of its children and can be added to child rows without double counting. That consolidation rule is **not** established for the real Everpure source.

The input CSVs have no label column. Their synthetic provenance is established by this isolated directory, this README, and the `SYN_` identifiers. Every generated demonstration CSV and its manifest carries the explicit label above. The fiscal-calendar validator rejects missing or duplicate indices, misordered rows, and non-increasing or invalid period-end dates before SQL runs.
