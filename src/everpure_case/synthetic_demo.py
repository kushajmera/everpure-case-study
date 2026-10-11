"""Isolated, executable revenue-decay methodology using invented observations."""

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from everpure_case.hierarchy import resolve_hierarchy

LABEL = "SYNTHETIC METHODOLOGY DEMONSTRATION — NOT OBSERVED EVERPURE REVENUE"


def validate_fiscal_calendar(calendar: pd.DataFrame) -> None:
    """Reject gaps, duplicate indices, and dates inconsistent with period order."""
    if calendar.empty:
        raise ValueError("Synthetic fiscal calendar has no periods")
    indices = pd.to_numeric(calendar.fiscal_period_index, errors="coerce")
    if (
        indices.isna().any()
        or not np.isfinite(indices.to_numpy(dtype=float)).all()
        or indices.mod(1).ne(0).any()
    ):
        raise ValueError("Synthetic fiscal-period indices must be finite integers")
    if indices.duplicated().any():
        raise ValueError("Synthetic fiscal-period indices must be unique")
    if not indices.is_monotonic_increasing:
        raise ValueError("Synthetic fiscal-period indices must be strictly ordered")
    if not indices.diff().iloc[1:].eq(1).all():
        raise ValueError("Synthetic fiscal-period indices must be consecutive")
    ends = pd.to_datetime(calendar.fiscal_period_end, format="%Y-%m-%d", errors="coerce")
    if ends.isna().any() or not ends.diff().dt.total_seconds().iloc[1:].gt(0).all():
        raise ValueError("Synthetic fiscal-period end dates must strictly increase")


def execute_synthetic_demo(repo_root: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate the separate fixture and run account and complete-root SQL."""
    root = Path(repo_root).resolve()
    fixture = root / "data/synthetic"
    members = pd.read_csv(fixture / "hierarchy.csv", dtype=str, keep_default_na=False)
    calendar = pd.read_csv(fixture / "fiscal_calendar.csv", parse_dates=["fiscal_period_end"])
    revenue = pd.read_csv(fixture / "account_period_revenue.csv", parse_dates=["fiscal_period_end"])
    validate_fiscal_calendar(calendar)
    if (
        members.account_id.duplicated().any()
        or revenue.duplicated(["account_id", "fiscal_period_index"]).any()
    ):
        raise ValueError("Synthetic fixture keys must be unique at their declared grains")
    if not np.isfinite(revenue.period_revenue_usd.to_numpy(dtype=float)).all():
        raise ValueError("Synthetic revenue must be finite")
    if revenue.period_revenue_usd.lt(0).any():
        raise ValueError("Synthetic revenue must be nonnegative")
    if not set(revenue.account_id).issubset(set(members.account_id)):
        raise ValueError("Synthetic revenue contains an unmapped account")
    checked_periods = revenue.merge(
        calendar,
        on="fiscal_period_index",
        how="left",
        suffixes=("", "_calendar"),
        validate="many_to_one",
    )
    if (
        checked_periods.fiscal_period_end_calendar.isna().any()
        or not checked_periods["fiscal_period_end"]
        .eq(checked_periods["fiscal_period_end_calendar"])
        .all()
    ):
        raise ValueError("Synthetic revenue period dates must match the calendar")
    members.insert(0, "source_row_number", range(2, len(members) + 2))
    members["account_id_key"] = members.account_id.str.strip()
    members["parent_account_id_key"] = members.parent_account_id.str.strip()
    mapping, exceptions = resolve_hierarchy(members)
    if not exceptions.empty:
        raise ValueError("Synthetic hierarchy must resolve uniquely")
    synthetic_hierarchy = mapping[["account_id", "root_account_id"]]
    if len(synthetic_hierarchy) != len(members):
        raise AssertionError("Synthetic hierarchy mapping changed the account count")
    connection = duckdb.connect(":memory:")
    try:
        connection.register("synthetic_hierarchy", synthetic_hierarchy)
        connection.register("synthetic_calendar", calendar)
        connection.register("synthetic_revenue", revenue)
        account = connection.execute(
            (root / "sql/synthetic_account_decay.sql").read_text(encoding="utf-8")
        ).df()
        groups = connection.execute(
            (root / "sql/synthetic_root_decay.sql").read_text(encoding="utf-8")
        ).df()
    finally:
        connection.close()
    if len(account) != len(revenue):
        raise AssertionError("Synthetic account observation coverage changed")
    if len(groups) != synthetic_hierarchy.root_account_id.nunique() * len(calendar):
        raise AssertionError("Synthetic root-period grid coverage changed")
    if (
        not account.demonstration_label.eq(LABEL).all()
        or not groups.demonstration_label.eq(LABEL).all()
    ):
        raise AssertionError("Synthetic output label missing")
    return account, groups


def run_synthetic_demo(repo_root: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write only under the separate synthetic-demo output folder."""
    account, groups = execute_synthetic_demo(repo_root)
    output = Path(repo_root).resolve() / "outputs/phase1/synthetic_demo"
    output.mkdir(parents=True, exist_ok=True)
    account.to_csv(output / "synthetic_account_decay.csv", index=False, float_format="%.8f")
    groups.to_csv(output / "synthetic_root_decay.csv", index=False, float_format="%.8f")
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "demonstration_label": LABEL,
                "source": "data/synthetic; no join to data/raw",
                "account_observation_rows": len(account),
                "root_period_rows": len(groups),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return account, groups


def main() -> None:
    parser = argparse.ArgumentParser(description=LABEL)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    account, groups = run_synthetic_demo(args.repo_root)
    print(f"{LABEL}: {len(account)} account observations, {len(groups)} root periods")


if __name__ == "__main__":
    main()
