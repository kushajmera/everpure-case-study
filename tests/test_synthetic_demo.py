import shutil
from pathlib import Path

import pandas as pd
import pytest

from everpure_case.synthetic_demo import LABEL, execute_synthetic_demo


def test_synthetic_account_decay_gap_zero_baseline_and_velocity():
    root = Path(__file__).resolve().parents[1]
    account, groups = execute_synthetic_demo(root)
    assert len(account) == 19
    assert len(groups) == 8
    assert account.demonstration_label.eq(LABEL).all()
    a2 = account.query("account_id == 'SYN_A' and fiscal_period_index == 2").iloc[0]
    assert a2.absolute_change_usd == -20
    assert a2.consecutive_pct_change == pytest.approx(-0.2)
    assert a2.signed_change_usd_per_period == -20
    b4 = account.query("account_id == 'SYN_B' and fiscal_period_index == 4").iloc[0]
    assert b4.previous_period_index == 2
    assert b4.elapsed_periods == 2
    assert b4.absolute_change_usd == 20
    assert pd.isna(b4.consecutive_pct_change)
    assert b4.signed_change_usd_per_period == 10
    assert b4.comparison_status == "nonconsecutive_gap"
    b2 = account.query("account_id == 'SYN_B' and fiscal_period_index == 2").iloc[0]
    assert b2.next_period_index == 4
    assert b4.observed_period_recency_rank == 1
    c2 = account.query("account_id == 'SYN_C' and fiscal_period_index == 2").iloc[0]
    assert c2.previous_revenue_usd == 0
    assert c2.absolute_change_usd == 20
    assert pd.isna(c2.consecutive_pct_change)
    assert c2.comparison_status == "consecutive_zero_baseline"


def test_synthetic_root_rollup_never_relabels_missing_as_zero():
    groups = execute_synthetic_demo(Path(__file__).resolve().parents[1])[1]
    r1q1 = groups.query("root_account_id == 'SYN_R1' and fiscal_period_index == 1").iloc[0]
    r1q2 = groups.query("root_account_id == 'SYN_R1' and fiscal_period_index == 2").iloc[0]
    r1q3 = groups.query("root_account_id == 'SYN_R1' and fiscal_period_index == 3").iloc[0]
    r1q4 = groups.query("root_account_id == 'SYN_R1' and fiscal_period_index == 4").iloc[0]
    r2q2 = groups.query("root_account_id == 'SYN_R2' and fiscal_period_index == 2").iloc[0]
    assert r1q1.root_revenue_usd == 150  # 0 + 100 + 50
    assert r1q2.root_revenue_usd == 130  # 0 + 80 + 50
    assert r1q2.consecutive_absolute_change_usd == -20
    assert r1q2.consecutive_pct_change == pytest.approx(-20 / 150)
    assert r1q3.observed_account_count == 2
    assert r1q3.expected_account_count == 3
    assert r1q3.observed_partial_revenue_usd == 60
    assert pd.isna(r1q3.root_revenue_usd)
    assert pd.isna(r1q4.consecutive_absolute_change_usd)
    assert r1q4.comparison_status == "incomplete_previous_period"
    assert r2q2.root_revenue_usd == 220  # 200 + 20
    assert r2q2.complete_root_spend_rank == 1


@pytest.mark.parametrize(
    ("indices", "dates", "message"),
    [
        ([1, 2, 4, 5], None, "consecutive"),
        ([1, 2, 2, 4], None, "unique"),
        ([2, 1, 3, 4], None, "strictly ordered"),
        (None, ["2024-03-31", "2024-09-30", "2024-06-30", "2024-12-31"], "strictly increase"),
        (None, ["2024-03-31", "2024-06-30", "2024-06-30", "2024-12-31"], "strictly increase"),
        (None, ["2024-03-31", "2024-06-30", "", "2024-12-31"], "strictly increase"),
    ],
)
def test_synthetic_calendar_rejects_gaps_duplicates_and_bad_order(
    isolated_repo, indices, dates, message
):
    source_root = Path(__file__).resolve().parents[1]
    fixture = isolated_repo / "data/synthetic"
    shutil.copytree(source_root / "data/synthetic", fixture)
    path = fixture / "fiscal_calendar.csv"
    calendar = pd.read_csv(path)
    if indices is not None:
        calendar["fiscal_period_index"] = indices
    if dates is not None:
        calendar["fiscal_period_end"] = dates
    calendar.to_csv(path, index=False)
    with pytest.raises(ValueError, match=message):
        execute_synthetic_demo(isolated_repo)
