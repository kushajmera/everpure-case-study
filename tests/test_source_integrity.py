from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from everpure_case.source_integrity import (
    EXPECTED_RECORDED_SPEND_USD,
    EXPECTED_SHA256,
    SourceIntegrityError,
    verify_authoritative_source,
)


def test_authoritative_source_matches_approved_baseline():
    result = verify_authoritative_source(Path(__file__).resolve().parents[1])
    assert result["source_sha256"] == EXPECTED_SHA256
    assert result["source_rows"] == 2000
    assert Decimal(result["raw_recorded_spend_usd"]) == EXPECTED_RECORDED_SPEND_USD


def test_one_cent_source_change_fails_hash_and_exact_spend(isolated_repo):
    path = isolated_repo / "data/raw/Case_Study_1_Install_Base_Reactivation.csv"
    source = pd.read_csv(path, dtype=str, keep_default_na=False)
    source.loc[0, "historical_spend_usd"] = str(
        Decimal(source.loc[0, "historical_spend_usd"]) + Decimal("0.01")
    )
    source.to_csv(path, index=False)
    with pytest.raises(SourceIntegrityError) as error:
        verify_authoritative_source(isolated_repo)
    assert "SHA-256" in str(error.value)
    assert "recorded spend expected 2541024291, observed 2541024291.01" in str(error.value)


def test_source_change_with_same_count_and_spend_fails_hash(isolated_repo):
    path = isolated_repo / "data/raw/Case_Study_1_Install_Base_Reactivation.csv"
    source = pd.read_csv(path, dtype=str, keep_default_na=False)
    source.loc[0, "region"] = "altered"
    source.to_csv(path, index=False)
    with pytest.raises(SourceIntegrityError, match="SHA-256"):
        verify_authoritative_source(isolated_repo)


def test_missing_source_row_fails_row_count(isolated_repo):
    path = isolated_repo / "data/raw/Case_Study_1_Install_Base_Reactivation.csv"
    source = pd.read_csv(path, dtype=str, keep_default_na=False)
    source.iloc[1:].to_csv(path, index=False)
    with pytest.raises(SourceIntegrityError, match="rows expected 2000, observed 1999"):
        verify_authoritative_source(isolated_repo)
