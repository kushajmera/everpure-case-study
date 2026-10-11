from io import StringIO

import pandas as pd
import pytest

from everpure_case.config import SOURCE_COLUMNS
from everpure_case.ingestion import SchemaError, read_source


def test_exact_schema_and_source_strings():
    row = {col: "" for col in SOURCE_COLUMNS}
    row.update(account_id="001", sfdc_health_score="nan", partner_managed="")
    content = pd.DataFrame([row], columns=SOURCE_COLUMNS).to_csv(index=False)
    frame = read_source(StringIO(content))
    assert frame.loc[0, "account_id"] == "001"
    assert frame.loc[0, "sfdc_health_score"] == "nan"
    assert frame.loc[0, "partner_managed"] == ""
    assert frame.loc[0, "source_row_number"] == 2


def test_schema_rejects_missing_column():
    content = pd.DataFrame([{"account_id": "A"}]).to_csv(index=False)
    with pytest.raises(SchemaError):
        read_source(StringIO(content))
