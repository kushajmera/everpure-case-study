import pandas as pd
from test_quality import fixture_rows

from everpure_case.hierarchy import parent_summary, resolve_hierarchy
from everpure_case.quality import clean_accounts


def make_accounts(pairs):
    rows = []
    for index, (key, parent, spend) in enumerate(pairs, start=2):
        row = (
            fixture_rows(account_id=key, parent_account_id=parent, historical_spend_usd=str(spend))
            .iloc[0]
            .to_dict()
        )
        row["source_row_number"] = index
        rows.append(row)
    return clean_accounts(pd.DataFrame(rows))[0]


def test_multilevel_root_and_additive_spend():
    accounts = make_accounts([("A", "", 10), ("B", "A", 20), ("C", "B", 30)])
    mapping, issues = resolve_hierarchy(accounts)
    assert issues.empty
    assert mapping.root_account_id.tolist() == ["A", "A", "A"]
    assert mapping.hierarchy_depth.tolist() == [0, 1, 2]
    summary = parent_summary(accounts, mapping)
    assert summary.loc[0, "additive_recorded_spend_usd"] == 60
    assert summary.loc[0, "direct_child_count"] == 1


def test_cycle_missing_parent_self_reference_and_duplicate():
    accounts = make_accounts(
        [
            ("A", "B", 1),
            ("B", "A", 2),
            ("C", "Z", 3),
            ("D", "D", 4),
            ("E", "", 5),
            ("E", "", 6),
        ]
    )
    mapping, issues = resolve_hierarchy(accounts)
    assert mapping.hierarchy_status.tolist() == [
        "cycle",
        "cycle",
        "missing_parent",
        "self_reference",
        "ambiguous_id",
        "ambiguous_id",
    ]
    assert len(issues) == 6
    assert parent_summary(accounts, mapping).empty
