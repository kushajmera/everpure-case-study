"""Read the CSV without changing source strings or row order."""

from pathlib import Path

import pandas as pd

from everpure_case.config import SOURCE_COLUMNS


class SchemaError(ValueError):
    """The source columns do not match the documented contract."""


def read_source(path: str | Path) -> pd.DataFrame:
    """Read every column as text; an empty string remains distinct from literal 'nan'."""
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if tuple(frame.columns) != SOURCE_COLUMNS:
        raise SchemaError(f"Expected columns {SOURCE_COLUMNS}; received {tuple(frame.columns)}")
    frame.insert(0, "source_row_number", range(2, len(frame) + 2))
    return frame
