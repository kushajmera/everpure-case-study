import hashlib

import pandas as pd
import pytest

import everpure_case.pipeline as pipeline_module
from everpure_case.ingestion import read_source
from everpure_case.pipeline import _has_consecutive_daily_steps, run_pipeline


@pytest.mark.parametrize(
    ("dates", "expected"),
    [
        (["2024-01-01", "2024-01-02", "2024-01-03"], True),
        (["2024-01-01", "2024-01-03", "2024-01-04"], False),
        (["2024-01-01", None, "2024-01-03", "2024-01-04"], True),
        (["2024-01-01", None, "2024-01-03", "2024-01-05"], False),
    ],
)
def test_daily_sequence_checks_valid_deltas_and_preserves_null_handling(dates, expected):
    parsed = pd.to_datetime(pd.Series(dates))
    assert _has_consecutive_daily_steps(parsed) is expected


def test_pipeline_reconciles_and_writes_deterministic_outputs(isolated_repo):
    root = isolated_repo
    source = read_source(root / "data/raw/Case_Study_1_Install_Base_Reactivation.csv")
    expected_spend = pd.to_numeric(source["historical_spend_usd"]).sum()
    first = run_pipeline(root)
    paths = sorted((root / "outputs/phase1").glob("*.csv"))
    paths.append(root / "outputs/phase1/metrics.json")
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    second = run_pipeline(root)
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    assert first == second
    assert before == after
    assert first["source_rows"] == len(source)
    assert first["booking_date_exact_account_id_sequence"] is True
    assert first["raw_recorded_spend_usd"] == expected_spend
    assert (
        first["resolved_additive_spend_usd"] + first["unresolved_recorded_spend_usd"]
        == expected_spend
    )
    assert first["sql_regional_spend_usd"] == expected_spend
    assert first["sql_root_spend_usd"] == first["resolved_additive_spend_usd"]
    account_quality = pd.read_csv(root / "outputs/phase1/account_quality_summary.csv")
    assert len(account_quality) == len(source)
    assert account_quality.exception_count.sum() == first["quality_exception_rows"]
    child_counts = pd.read_csv(root / "outputs/phase1/direct_child_counts.csv")
    assert child_counts.direct_child_count.sum() == first["direct_child_rows"]
    sensitivity = pd.read_csv(root / "outputs/phase1/analysis_date_sensitivity.csv")
    raw_dates = pd.to_datetime(source.last_booking_date)
    for row in sensitivity.itertuples(index=False):
        cutoff = pd.Timestamp(row.analysis_as_of_date) - pd.DateOffset(years=2)
        assert row.calendar_2y_proxy_eligible_rows == int(raw_dates.le(cutoff).sum())
    parent_comparison = pd.read_csv(root / "outputs/phase1/parent_child_spend_comparison.csv")
    assert (
        parent_comparison.parent_below_direct_child_sum.sum()
        == first["parent_rows_below_direct_child_sum"]
    )


def test_invalid_booking_date_keeps_account_and_excludes_only_window_row(isolated_repo):
    root = isolated_repo
    path = root / "data/raw/Case_Study_1_Install_Base_Reactivation.csv"
    source = pd.read_csv(path, dtype=str, keep_default_na=False)
    target_id = source.loc[0, "account_id"]
    source.loc[0, "last_booking_date"] = "invalid-date"
    source.to_csv(path, index=False)
    metrics = run_pipeline(root)
    cleaned = pd.read_csv(root / "outputs/phase1/cleaned_accounts.csv")
    windows = pd.read_csv(root / "outputs/phase1/window_analytics.csv")
    exceptions = pd.read_csv(root / "outputs/phase1/data_quality_exceptions.csv")
    assert metrics["source_rows"] == 2000
    assert len(cleaned) == 2000
    assert len(windows) == 1999
    assert target_id in set(cleaned.account_id)
    assert target_id not in set(windows.account_id)
    assert ((exceptions.account_id.eq(target_id)) & exceptions.issue_code.eq("INVALID_DATE")).any()
    assert metrics["unresolved_hierarchy_rows"] == 0


def test_fractional_cents_reconcile_without_hiding_one_cent_error(isolated_repo):
    from everpure_case.pipeline import _money_cents

    root = isolated_repo
    path = root / "data/raw/Case_Study_1_Install_Base_Reactivation.csv"
    source = pd.read_csv(path, dtype=str, keep_default_na=False)
    source.loc[0, "historical_spend_usd"] = "0.10"
    source.loc[1, "historical_spend_usd"] = "0.20"
    source.to_csv(path, index=False)
    metrics = run_pipeline(root)
    assert _money_cents(metrics["raw_recorded_spend_usd"]) == _money_cents(
        metrics["sql_root_spend_usd"]
    )
    assert _money_cents(0.1 + 0.2) == _money_cents(0.3)
    assert _money_cents(0.3) != _money_cents(0.31)


def test_one_cent_sql_discrepancy_fails_reconciliation(isolated_repo, monkeypatch):
    original_run_queries = pipeline_module.run_queries

    def altered_queries(*args, **kwargs):
        results = original_run_queries(*args, **kwargs)
        results["regional_spend"].loc[0, "recorded_spend_usd"] += 0.01
        return results

    monkeypatch.setattr(pipeline_module, "run_queries", altered_queries)
    with pytest.raises(AssertionError, match="Regional SQL spend reconciliation failed"):
        run_pipeline(isolated_repo)


def test_nonfinite_source_spend_is_flagged_and_does_not_crash(isolated_repo):
    root = isolated_repo
    path = root / "data/raw/Case_Study_1_Install_Base_Reactivation.csv"
    source = pd.read_csv(path, dtype=str, keep_default_na=False)
    target_id = source.loc[0, "account_id"]
    source.loc[0, "historical_spend_usd"] = "inf"
    source.to_csv(path, index=False)
    metrics = run_pipeline(root)
    cleaned = pd.read_csv(root / "outputs/phase1/cleaned_accounts.csv", dtype=str)
    exceptions = pd.read_csv(root / "outputs/phase1/data_quality_exceptions.csv")
    assert metrics["source_rows"] == 2000
    assert metrics["spend_rows_without_finite_numeric_value"] == 1
    assert cleaned.loc[cleaned.account_id.eq(target_id), "historical_spend_usd"].iloc[0] == "inf"
    assert (
        (exceptions.account_id.eq(target_id)) & exceptions.issue_code.eq("NON_FINITE_NUMBER")
    ).any()
