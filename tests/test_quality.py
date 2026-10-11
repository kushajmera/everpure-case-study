from datetime import date

import pandas as pd

from everpure_case.config import SOURCE_COLUMNS
from everpure_case.quality import clean_accounts, eligibility_reconciliation


def fixture_rows(**updates):
    row = dict.fromkeys(SOURCE_COLUMNS, "")
    row.update(
        account_id="A",
        region=" emea - france ",
        last_booking_date="2024-10-09",
        contract_start_date="2020-01-01",
        years_inactive="1.0",
        historical_spend_usd="100",
        discount_tier_pct="0.25",
        sfdc_health_score="Missing",
        partner_managed="",
        open_support_tickets="999",
        monthly_usage_gb="0",
    )
    row.update(updates)
    return pd.DataFrame([{"source_row_number": 2, **row}])


def test_missing_sentinel_zero_and_normalization():
    clean, exceptions = clean_accounts(fixture_rows())
    row = clean.iloc[0]
    assert row.region_clean == "EMEA - France"
    assert pd.isna(row.health_clean) and pd.isna(row.partner_managed_clean)
    assert pd.isna(row.tickets_clean) and row.ticket_sentinel
    assert row.monthly_usage_gb_num == 0
    assert row.discount_tier_pct_num == 0.25
    assert set(exceptions.issue_code) >= {
        "REGION_NORMALIZED",
        "UNKNOWN_HEALTH",
        "UNRESOLVED_PARTNER",
        "TICKET_SENTINEL_999",
    }


def test_date_cutoff_and_contradiction():
    one = fixture_rows(last_booking_date="2024-10-09", years_inactive="1.0")
    two = fixture_rows(account_id="B", last_booking_date="2024-10-10", years_inactive="2.0")
    two["source_row_number"] = 3
    clean, exceptions = clean_accounts(pd.concat([one, two], ignore_index=True), date(2026, 10, 9))
    assert clean["calendar_2y_proxy_eligible"].tolist() == [True, False]
    assert clean["eligibility_disagrees"].tolist() == [True, True]
    assert len(exceptions.query("issue_code == 'INACTIVITY_CONTRADICTION'")) == 2
    assert eligibility_reconciliation(clean).account_rows.sum() == 2


def test_duplicate_invalid_date_and_number_are_flagged():
    one = fixture_rows(last_booking_date="bad", historical_spend_usd="-1")
    two = fixture_rows(region="Nowhere", open_support_tickets="0")
    two["source_row_number"] = 3
    _, exceptions = clean_accounts(pd.concat([one, two], ignore_index=True))
    assert len(exceptions.query("issue_code == 'DUPLICATE_ACCOUNT_ID'")) == 2
    assert set(exceptions.issue_code) >= {"INVALID_DATE", "OUT_OF_RANGE", "UNKNOWN_REGION"}
    assert (
        "TICKET_SENTINEL_999"
        not in exceptions.loc[exceptions.source_row_number.eq(3), "issue_code"].tolist()
    )


def test_all_eligibility_comparison_states_and_unknown_is_not_agreement():
    rows = [
        fixture_rows(account_id="A", last_booking_date="2020-01-01", years_inactive="3.0"),
        fixture_rows(account_id="B", last_booking_date="2026-01-01", years_inactive="1.0"),
        fixture_rows(account_id="C", last_booking_date="2020-01-01", years_inactive="1.0"),
        fixture_rows(account_id="D", last_booking_date="2020-01-01", years_inactive=""),
        fixture_rows(account_id="E", last_booking_date="bad-date", years_inactive="3.0"),
    ]
    source = pd.concat(rows, ignore_index=True)
    source["source_row_number"] = range(2, 7)
    clean, _ = clean_accounts(source)
    assert clean.eligibility_comparison_status.tolist() == [
        "agree_eligible",
        "agree_ineligible",
        "disagree",
        "unknown",
        "unknown",
    ]
    assert clean.eligibility_disagrees.tolist() == [False, False, True, False, False]


def test_inactivity_exception_comparison_is_not_a_replacement():
    clean, exceptions = clean_accounts(
        fixture_rows(last_booking_date="2019-01-01", years_inactive="0.5")
    )
    rows = exceptions.loc[
        exceptions.issue_code.isin(["INACTIVITY_VALUE_GAP_6M", "INACTIVITY_CONTRADICTION"])
    ]
    assert len(rows) == 2
    assert rows.cleaned_value.eq("").all()
    assert rows.comparison_value.ne("").all()
    assert clean.loc[0, "years_inactive"] == "0.5"
    assert clean.loc[0, "years_inactive_num"] == 0.5


def test_nonfinite_numeric_and_missing_discount_have_distinct_issues():
    one = fixture_rows(historical_spend_usd="inf", discount_tier_pct="")
    two = fixture_rows(account_id="B", historical_spend_usd="-inf", discount_tier_pct="nan")
    two["source_row_number"] = 3
    clean, exceptions = clean_accounts(pd.concat([one, two], ignore_index=True))
    assert clean.historical_spend_usd_num.isna().all()
    assert set(exceptions.issue_code) >= {"NON_FINITE_NUMBER", "MISSING_NUMBER"}
    assert not exceptions.issue_code.eq("OUT_OF_RANGE").any()
    first_discount = exceptions.loc[
        exceptions.source_row_number.eq(2) & exceptions.field.eq("discount_tier_pct")
    ]
    assert first_discount.issue_code.tolist() == ["MISSING_NUMBER"]
