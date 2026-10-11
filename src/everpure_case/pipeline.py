"""Run all Phase 1 observed-data analyses and write reproducible CSV artifacts."""

import argparse
import hashlib
import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import duckdb
import pandas as pd

from everpure_case.config import DEFAULT_AS_OF, OUTPUT_RELATIVE_PATH, SOURCE_RELATIVE_PATH
from everpure_case.hierarchy import parent_summary, resolve_hierarchy
from everpure_case.ingestion import read_source
from everpure_case.quality import (
    analysis_date_sensitivity,
    clean_accounts,
    eligibility_reconciliation,
)
from everpure_case.sql_analysis import run_queries


def _as_int(value: object) -> int:
    return int(value)


def _money_cents(value: object) -> int:
    """Round a computed amount to cents before reconciling financial totals."""
    decimal_value = Decimal(str(value))
    if not decimal_value.is_finite():
        raise AssertionError(f"Non-finite financial total: {value}")
    return int((decimal_value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _money_json(value: object) -> int | float:
    cents = _money_cents(value)
    return cents // 100 if cents % 100 == 0 else cents / 100


def _has_consecutive_daily_steps(dates: pd.Series) -> bool:
    """Check observed adjacent date deltas; null-adjacent deltas remain excluded."""
    return bool(dates.diff().dt.total_seconds().dropna().eq(86_400).all())


def run_pipeline(repo_root: str | Path, as_of: date = DEFAULT_AS_OF) -> dict[str, object]:
    root = Path(repo_root).resolve()
    source_path = root / SOURCE_RELATIVE_PATH
    output = root / OUTPUT_RELATIVE_PATH
    output.mkdir(parents=True, exist_ok=True)
    raw = read_source(source_path)
    accounts, quality_exceptions = clean_accounts(raw, as_of)
    hierarchy, hierarchy_exceptions = resolve_hierarchy(accounts)
    summary = parent_summary(accounts, hierarchy)
    summary["mean_recorded_spend_per_account_usd"] = (
        summary["additive_recorded_spend_usd"] / summary["account_count"]
    )
    direct_child_counts = (
        accounts.loc[accounts["parent_account_id_key"].ne("")]
        .groupby("parent_account_id_key")
        .size()
        .rename("direct_child_count")
        .reset_index()
        .rename(columns={"parent_account_id_key": "parent_account_id"})
        .sort_values("parent_account_id")
        .reset_index(drop=True)
    )
    reconciliation = eligibility_reconciliation(accounts)
    sensitivity = analysis_date_sensitivity(accounts["last_booking_date_parsed"], as_of)
    child_totals = (
        accounts.loc[accounts["parent_account_id_key"].ne("")]
        .groupby("parent_account_id_key")
        .agg(
            direct_child_count=("account_id", "size"),
            direct_child_recorded_spend_usd=("historical_spend_usd_num", "sum"),
        )
        .reset_index()
        .rename(columns={"parent_account_id_key": "parent_account_id"})
    )
    unique_parents = accounts.loc[
        ~accounts["account_id_key"].duplicated(keep=False),
        ["account_id_key", "historical_spend_usd_num"],
    ].rename(
        columns={
            "account_id_key": "parent_account_id",
            "historical_spend_usd_num": "parent_row_recorded_spend_usd",
        }
    )
    parent_comparison = child_totals.merge(
        unique_parents, on="parent_account_id", how="left", validate="one_to_one"
    )
    parent_comparison["parent_below_direct_child_sum"] = (
        parent_comparison["parent_row_recorded_spend_usd"]
        < parent_comparison["direct_child_recorded_spend_usd"]
    )
    parent_comparison = parent_comparison.sort_values("parent_account_id").reset_index(drop=True)
    queries = run_queries(accounts, hierarchy, root / "sql")
    hierarchy_sql = duckdb.connect(":memory:")
    try:
        hierarchy_sql.register("accounts", accounts)
        hierarchy_sql.register("hierarchy", hierarchy)
        hierarchy_sql_result = hierarchy_sql.execute(
            (root / "sql/account_hierarchy.sql").read_text(encoding="utf-8")
        ).df()
    finally:
        hierarchy_sql.close()

    if len(raw) != len(accounts) or len(raw) != len(hierarchy):
        raise AssertionError("Account row count changed")
    if not raw[raw.columns].equals(accounts[raw.columns]):
        raise AssertionError("Source values or row identity changed")
    resolved = hierarchy["hierarchy_status"].eq("resolved")
    raw_spend = accounts["historical_spend_usd_num"].sum()
    resolved_spend = summary["additive_recorded_spend_usd"].sum()
    unresolved_spend = accounts.loc[~resolved, "historical_spend_usd_num"].sum()
    if _money_cents(raw_spend) != _money_cents(resolved_spend + unresolved_spend):
        raise AssertionError("Hierarchy spend reconciliation failed")
    if _money_cents(queries["regional_spend"]["recorded_spend_usd"].sum()) != _money_cents(
        raw_spend
    ):
        raise AssertionError("Regional SQL spend reconciliation failed")
    if _money_cents(
        queries["spend_concentration"]["additive_recorded_spend_usd"].sum()
    ) != _money_cents(resolved_spend):
        raise AssertionError("Root SQL spend reconciliation failed")
    if _money_cents(hierarchy_sql_result["additive_recorded_spend_usd"].sum()) != _money_cents(
        resolved_spend
    ):
        raise AssertionError("Hierarchy SQL spend reconciliation failed")
    valid_window_rows = int((resolved & accounts["last_booking_date_parsed"].notna()).sum())
    if len(queries["window_analytics"]) != valid_window_rows:
        raise AssertionError("Booking window account coverage failed")

    # Hierarchy errors join the field-level register without changing its required schema.
    hierarchy_quality = pd.DataFrame(
        [
            {
                "source_row_number": row.source_row_number,
                "account_id": row.account_id,
                "field": "parent_account_id",
                "raw_value": row.parent_account_id,
                "cleaned_value": "",
                "comparison_value": "",
                "issue_code": row.issue_code,
                "severity": "error",
                "resolution": row.resolution,
            }
            for row in hierarchy_exceptions.itertuples(index=False)
        ],
        columns=quality_exceptions.columns,
    )
    exceptions = pd.concat([quality_exceptions, hierarchy_quality], ignore_index=True)
    exceptions = exceptions.sort_values(["source_row_number", "field", "issue_code"]).reset_index(
        drop=True
    )
    account_quality = accounts[["source_row_number", "account_id"]].merge(
        exceptions.groupby("source_row_number")
        .agg(
            exception_count=("issue_code", "size"),
            manual_review_count=("resolution", lambda x: int(x.eq("manual_review").sum())),
            left_unknown_count=("resolution", lambda x: int(x.eq("left_unknown").sum())),
            auto_resolved_count=("resolution", lambda x: int(x.eq("auto_resolved").sum())),
        )
        .reset_index(),
        on="source_row_number",
        how="left",
        validate="one_to_one",
    )
    count_cols = [
        "exception_count",
        "manual_review_count",
        "left_unknown_count",
        "auto_resolved_count",
    ]
    account_quality[count_cols] = account_quality[count_cols].fillna(0).astype(int)
    account_quality["needs_manual_review"] = account_quality["manual_review_count"].gt(0)
    account_quality["has_manual_review_exceptions"] = account_quality["needs_manual_review"]

    def save(frame: pd.DataFrame, name: str) -> None:
        frame.to_csv(output / name, index=False, encoding="utf-8", float_format="%.8f")

    save(accounts, "cleaned_accounts.csv")
    save(exceptions, "data_quality_exceptions.csv")
    save(account_quality, "account_quality_summary.csv")
    save(reconciliation, "inactivity_reconciliation.csv")
    save(sensitivity, "analysis_date_sensitivity.csv")
    save(hierarchy, "account_hierarchy.csv")
    save(direct_child_counts, "direct_child_counts.csv")
    save(parent_comparison, "parent_child_spend_comparison.csv")
    save(summary, "parent_spend_summary.csv")
    save(hierarchy_exceptions, "hierarchy_exceptions.csv")
    save(hierarchy_sql_result, "hierarchy_sql_summary.csv")
    for name, frame in queries.items():
        save(frame, f"{name}.csv")

    parent_ids = set(accounts["parent_account_id_key"]) - {""}
    source_reported = accounts["reported_2y_eligible"]
    date_proxy = accounts["calendar_2y_proxy_eligible"]
    numeric_ids = pd.to_numeric(
        accounts["account_id_key"].str.extract(r"^ACC_(\d+)$")[0], errors="coerce"
    )
    expected_booking_dates = pd.Timestamp(2019, 1, 1) + pd.to_timedelta(
        numeric_ids - 1000, unit="D"
    )
    metrics = {
        "analysis_as_of_date": as_of.isoformat(),
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "source_rows": len(raw),
        "unique_account_ids": int(accounts["account_id_key"].nunique()),
        "duplicate_account_rows": int(accounts["account_id_key"].duplicated(keep=False).sum()),
        "root_account_rows": int(accounts["parent_account_id_key"].eq("").sum()),
        "direct_child_rows": int(accounts["parent_account_id_key"].ne("").sum()),
        "distinct_direct_parent_ids": len(parent_ids),
        "resolved_hierarchy_rows": _as_int(resolved.sum()),
        "unresolved_hierarchy_rows": _as_int((~resolved).sum()),
        "max_hierarchy_depth": int(hierarchy["hierarchy_depth"].max()) if resolved.any() else None,
        "raw_recorded_spend_usd": _money_json(raw_spend),
        "spend_rows_without_finite_numeric_value": int(
            accounts["historical_spend_usd_num"].isna().sum()
        ),
        "resolved_additive_spend_usd": _money_json(resolved_spend),
        "unresolved_recorded_spend_usd": _money_json(unresolved_spend),
        "raw_region_variants": int(accounts["region"].nunique()),
        "canonical_regions": int(accounts["region_clean"].nunique()),
        "health_unknown_rows": int(accounts["health_clean"].isna().sum()),
        "partner_unknown_rows": int(accounts["partner_managed_clean"].isna().sum()),
        "ticket_sentinel_rows": int(accounts["ticket_sentinel"].sum()),
        "valid_zero_ticket_rows": int(accounts["tickets_clean"].eq(0).sum()),
        "reported_inactivity_missing_rows": int(accounts["years_inactive_missing"].sum()),
        "reported_2y_eligible_rows": int(source_reported.eq(True).sum()),
        "reported_under_2y_rows": int(source_reported.eq(False).sum()),
        "calendar_2y_proxy_eligible_rows": int(date_proxy.eq(True).sum()),
        "calendar_under_2y_proxy_rows": int(date_proxy.eq(False).sum()),
        "eligibility_disagreement_rows": int(accounts["eligibility_disagrees"].sum()),
        "eligibility_comparison_status_counts": {
            str(k): int(v)
            for k, v in accounts["eligibility_comparison_status"].value_counts().items()
        },
        "inactivity_value_mismatch_rows": int(accounts["inactivity_value_mismatch"].sum()),
        "booking_min": str(accounts["last_booking_date_parsed"].min().date()),
        "booking_max": str(accounts["last_booking_date_parsed"].max().date()),
        "contract_min": str(accounts["contract_start_date_parsed"].min().date()),
        "contract_max": str(accounts["contract_start_date_parsed"].max().date()),
        "booking_sequential_daily": _has_consecutive_daily_steps(
            accounts["last_booking_date_parsed"]
        ),
        "booking_date_exact_account_id_sequence": bool(
            numeric_ids.notna().all()
            and accounts["last_booking_date_parsed"].eq(expected_booking_dates).all()
        ),
        "contract_sequential_daily": _has_consecutive_daily_steps(
            accounts["contract_start_date_parsed"]
        ),
        "contract_to_booking_days_unique": sorted(
            int(x)
            for x in (accounts["last_booking_date_parsed"] - accounts["contract_start_date_parsed"])
            .dt.days.dropna()
            .unique()
        ),
        "parent_partner_conflict_groups": int(summary["partner_ownership_conflict"].sum()),
        "parent_multi_region_groups": int(summary["multi_region"].sum()),
        "parent_health_conflict_groups": int(summary["health_metadata_conflict"].sum()),
        "referenced_parents_with_spend_comparison": int(
            parent_comparison["parent_row_recorded_spend_usd"].notna().sum()
        ),
        "parent_rows_below_direct_child_sum": int(
            parent_comparison["parent_below_direct_child_sum"].sum()
        ),
        "root_group_size_spend_correlation": float(
            summary["account_count"].corr(summary["additive_recorded_spend_usd"])
        ),
        "quality_exception_rows": len(exceptions),
        "accounts_with_quality_exceptions": int(exceptions["account_id"].nunique()),
        "issue_counts": {
            str(k): int(v) for k, v in exceptions["issue_code"].value_counts().items()
        },
        "sql_regional_spend_usd": _money_json(
            queries["regional_spend"]["recorded_spend_usd"].sum()
        ),
        "sql_root_spend_usd": _money_json(
            queries["spend_concentration"]["additive_recorded_spend_usd"].sum()
        ),
    }
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Everpure Phase 1 observed-data analysis")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--as-of", type=date.fromisoformat, default=DEFAULT_AS_OF)
    args = parser.parse_args()
    print(json.dumps(run_pipeline(args.repo_root, args.as_of), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
