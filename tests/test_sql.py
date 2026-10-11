from pathlib import Path

import pandas as pd
from test_hierarchy import make_accounts

from everpure_case.hierarchy import resolve_hierarchy
from everpure_case.quality import clean_accounts
from everpure_case.sql_analysis import run_queries

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def test_booking_neighbors_are_actual_date_gaps():
    accounts = make_accounts([("A", "", 10), ("B", "A", 20), ("C", "A", 30)])
    accounts.loc[:, "last_booking_date_parsed"] = pd.to_datetime(
        [
            "2020-01-01",
            "2020-01-05",
            "2020-01-09",
        ]
    )
    mapping, _ = resolve_hierarchy(accounts)
    results = run_queries(accounts, mapping, SQL_DIR)
    window = results["window_analytics"]
    assert window.days_since_previous_account_booking.tolist()[1:] == [4, 4]
    assert window.days_until_next_account_booking.tolist()[:2] == [4, 4]
    assert window.recency_rank_within_root.tolist() == [3, 2, 1]
    assert results["spend_concentration"].additive_recorded_spend_usd.sum() == 60
    assert results["regional_spend"].recorded_spend_usd.sum() == 60


def test_booking_order_is_independent_of_account_id_order():
    accounts = make_accounts([("A", "", 10), ("B", "A", 20), ("C", "A", 30)])
    accounts.loc[:, "last_booking_date_parsed"] = pd.to_datetime(
        ["2020-01-05", "2020-01-11", "2020-01-01"]
    )
    mapping, _ = resolve_hierarchy(accounts)
    window = run_queries(accounts, mapping, SQL_DIR)["window_analytics"]
    assert window.account_id.tolist() == ["C", "A", "B"]
    assert window.days_since_previous_account_booking.tolist()[1:] == [4, 6]
    assert window.recency_rank_within_root.tolist() == [3, 2, 1]


def test_unresolved_root_has_no_shared_null_root_rank():
    accounts = make_accounts([("A", "", 10), ("B", "Z", 20), ("C", "Y", 30)])
    mapping, _ = resolve_hierarchy(accounts)
    features = run_queries(accounts, mapping, SQL_DIR)["account_opportunity"]
    assert features.loc[features.account_id.eq("A"), "root_recorded_spend_rank"].iloc[0] == 1
    assert features.loc[features.account_id.ne("A"), "root_recorded_spend_rank"].isna().all()
    assert features.loc[features.account_id.ne("A"), "hierarchy_unresolved"].all()


def test_sql_and_pandas_group_totals_match_for_actual_source():
    from everpure_case.ingestion import read_source

    root = Path(__file__).resolve().parents[1]
    accounts, _ = clean_accounts(
        read_source(root / "data/raw/Case_Study_1_Install_Base_Reactivation.csv")
    )
    mapping, _ = resolve_hierarchy(accounts)
    results = run_queries(accounts, mapping, SQL_DIR)
    expected = accounts.historical_spend_usd_num.sum()
    assert results["regional_spend"].recorded_spend_usd.sum() == expected
    assert results["spend_concentration"].additive_recorded_spend_usd.sum() == expected
    assert results["account_opportunity"].recorded_spend_usd.sum() == expected
    assert len(results["window_analytics"]) == len(accounts)


def test_cleaning_and_hierarchy_are_deterministic():
    raw = make_accounts([("A", "", 10), ("B", "A", 20)])
    first, first_issues = clean_accounts(
        raw[
            [
                "source_row_number",
                "account_id",
                "parent_account_id",
                "region",
                "last_booking_date",
                "contract_start_date",
                "years_inactive",
                "historical_spend_usd",
                "discount_tier_pct",
                "sfdc_health_score",
                "partner_managed",
                "open_support_tickets",
                "monthly_usage_gb",
            ]
        ]
    )
    second, second_issues = clean_accounts(
        raw[
            [
                "source_row_number",
                "account_id",
                "parent_account_id",
                "region",
                "last_booking_date",
                "contract_start_date",
                "years_inactive",
                "historical_spend_usd",
                "discount_tier_pct",
                "sfdc_health_score",
                "partner_managed",
                "open_support_tickets",
                "monthly_usage_gb",
            ]
        ]
    )
    pd.testing.assert_frame_equal(first, second)
    pd.testing.assert_frame_equal(first_issues, second_issues)
    pd.testing.assert_frame_equal(resolve_hierarchy(first)[0], resolve_hierarchy(second)[0])
