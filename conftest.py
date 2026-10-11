"""Skip tests that need the confidential assessment CSV when it is not present (Path B)."""

from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parent / "data/raw/Case_Study_1_Install_Base_Reactivation.csv"
SOURCE_DEPENDENT = {
    "test_phase2_pipeline.py",
    "test_phase3_financial.py",
    "test_phase4_routing.py",
    "test_pipeline.py",
    "test_reactivation_scenarios.py",
    "test_source_integrity.py",
}
SOURCE_DEPENDENT_TESTS = {"test_sql_and_pandas_group_totals_match_for_actual_source"}


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
