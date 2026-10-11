"""Resolve arbitrary-depth parent links without duplicating account spend."""

import pandas as pd

HIERARCHY_EXCEPTION_COLUMNS = [
    "source_row_number",
    "account_id",
    "parent_account_id",
    "issue_code",
    "detail",
    "resolution",
]


def resolve_hierarchy(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return one mapping per source row and explicit unresolved paths."""
    ids = frame["account_id_key"].tolist()
    parents = frame["parent_account_id_key"].tolist()
    counts = pd.Series(ids).value_counts()
    ambiguous = {key for key, count in counts.items() if count > 1 and key}
    lookup = {
        key: parent
        for key, parent in zip(ids, parents, strict=True)
        if key and key not in ambiguous
    }
    memo: dict[str, tuple[str | None, int | None, str]] = {}

    def walk(key: str, seen: frozenset[str]) -> tuple[str | None, int | None, str]:
        if key in memo:
            return memo[key]
        if key in seen:
            return None, None, "cycle"
        if key in ambiguous:
            return None, None, "ambiguous_id"
        if key not in lookup:
            return None, None, "missing_parent"
        parent = lookup[key]
        if not parent:
            result = (key, 0, "resolved")
        elif parent == key:
            result = (None, None, "self_reference")
        else:
            root, depth, status = walk(parent, seen | {key})
            result = (root, depth + 1, status) if status == "resolved" else (None, None, status)
        memo[key] = result
        return result

    records = []
    for row in frame.itertuples(index=False):
        key = row.account_id_key
        root, depth, status = walk(key, frozenset()) if key else (None, None, "missing_id")
        records.append(
            {
                "source_row_number": row.source_row_number,
                "account_id": row.account_id,
                "parent_account_id": row.parent_account_id,
                "root_account_id": root,
                "hierarchy_depth": depth,
                "hierarchy_status": status,
            }
        )
    mapping = pd.DataFrame(records)
    unresolved = mapping.loc[mapping["hierarchy_status"].ne("resolved")]
    exceptions = pd.DataFrame(
        [
            {
                "source_row_number": row.source_row_number,
                "account_id": row.account_id,
                "parent_account_id": row.parent_account_id,
                "issue_code": row.hierarchy_status.upper(),
                "detail": "Root cannot be identified uniquely from source parent links",
                "resolution": "manual_review",
            }
            for row in unresolved.itertuples(index=False)
        ],
        columns=HIERARCHY_EXCEPTION_COLUMNS,
    )
    return mapping, exceptions


def parent_summary(frame: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    """Sum each resolved source row once; result is an additive recorded-spend proxy."""
    joined = frame.merge(
        mapping[["source_row_number", "root_account_id", "hierarchy_status", "hierarchy_depth"]],
        on="source_row_number",
        validate="one_to_one",
    )
    resolved = joined.loc[joined["hierarchy_status"].eq("resolved")].copy()
    summary = (
        resolved.groupby("root_account_id", dropna=False)
        .agg(
            account_count=("account_id", "size"),
            direct_child_count=("hierarchy_depth", lambda x: int(x.eq(1).sum())),
            max_depth=("hierarchy_depth", "max"),
            additive_recorded_spend_usd=("historical_spend_usd_num", "sum"),
            latest_booking_date=("last_booking_date_parsed", "max"),
            region_count=("region_clean", "nunique"),
            known_partner_states=("partner_managed_clean", "nunique"),
            unknown_partner_count=("partner_managed_clean", lambda x: int(x.isna().sum())),
            unknown_health_count=("health_clean", lambda x: int(x.isna().sum())),
            known_health_states=("health_clean", "nunique"),
        )
        .reset_index()
    )
    summary["partner_ownership_conflict"] = summary["known_partner_states"].gt(1)
    summary["multi_region"] = summary["region_count"].gt(1)
    summary["health_metadata_conflict"] = summary["known_health_states"].gt(1)
    summary = summary.sort_values(
        ["additive_recorded_spend_usd", "root_account_id"], ascending=[False, True]
    ).reset_index(drop=True)
    return summary
