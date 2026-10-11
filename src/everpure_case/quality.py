"""Field-level diagnostics and explicitly labeled analytical proxies."""

from datetime import date

import numpy as np
import pandas as pd

from everpure_case.config import DEFAULT_AS_OF, REGION_MAP

EXCEPTION_COLUMNS = [
    "source_row_number",
    "account_id",
    "field",
    "raw_value",
    "cleaned_value",
    "comparison_value",
    "issue_code",
    "severity",
    "resolution",
]


def normalize_region(raw: str) -> str | None:
    return REGION_MAP.get(" ".join(raw.split()).casefold())


def calendar_2y_proxy(booking_dates: pd.Series, as_of: date) -> pd.Series:
    """Two-calendar-year proxy; unknown booking dates stay unknown."""
    cutoff = pd.Timestamp(as_of) - pd.DateOffset(years=2)
    result = booking_dates.le(cutoff).astype("boolean")
    result.loc[booking_dates.isna()] = pd.NA
    return result


def analysis_date_sensitivity(booking_dates: pd.Series, as_of: date) -> pd.DataFrame:
    """Reapply the same calendar proxy at selected snapshots, including the configured date."""
    dates = sorted({date(2024, 6, 22), date(2025, 6, 22), date(2026, 6, 22), as_of})
    rows = []
    for snapshot in dates:
        eligible = calendar_2y_proxy(booking_dates, snapshot)
        rows.append(
            {
                "analysis_as_of_date": snapshot.isoformat(),
                "calendar_2y_proxy_eligible_rows": int(eligible.eq(True).sum()),
                "calendar_2y_proxy_ineligible_rows": int(eligible.eq(False).sum()),
                "unknown_booking_date_rows": int(eligible.isna().sum()),
            }
        )
    return pd.DataFrame(rows)


def clean_accounts(
    source: pd.DataFrame, as_of: date = DEFAULT_AS_OF
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retain all source columns; add typed fields and an exception for each anomaly."""
    frame = source.copy()
    issues: list[dict] = []

    def issue(
        row: pd.Series,
        field: str,
        cleaned: object,
        code: str,
        severity: str,
        resolution: str,
        comparison: object = None,
    ) -> None:
        issues.append(
            {
                "source_row_number": int(row["source_row_number"]),
                "account_id": row["account_id"],
                "field": field,
                "raw_value": row[field],
                "cleaned_value": "" if pd.isna(cleaned) else str(cleaned),
                "comparison_value": "" if pd.isna(comparison) else str(comparison),
                "issue_code": code,
                "severity": severity,
                "resolution": resolution,
            }
        )

    frame["region_clean"] = frame["region"].map(normalize_region)
    for _, row in frame.iterrows():
        if pd.isna(row["region_clean"]):
            issue(row, "region", None, "UNKNOWN_REGION", "error", "manual_review")
        elif row["region"] != row["region_clean"]:
            issue(row, "region", row["region_clean"], "REGION_NORMALIZED", "info", "auto_resolved")

    for col in ("last_booking_date", "contract_start_date"):
        frame[col + "_parsed"] = pd.to_datetime(frame[col], format="%Y-%m-%d", errors="coerce")
        for _, row in frame.loc[frame[col + "_parsed"].isna()].iterrows():
            issue(row, col, None, "INVALID_DATE", "error", "manual_review")

    for col in (
        "years_inactive",
        "historical_spend_usd",
        "discount_tier_pct",
        "open_support_tickets",
        "monthly_usage_gb",
    ):
        frame[col + "_num"] = pd.to_numeric(frame[col], errors="coerce")
        nonfinite = frame[col].str.strip().str.casefold().isin(
            {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}
        ) | np.isinf(frame[col + "_num"].to_numpy(dtype=float))
        for _, row in frame.loc[nonfinite].iterrows():
            issue(row, col, None, "NON_FINITE_NUMBER", "error", "manual_review")
        frame.loc[nonfinite, col + "_num"] = np.nan
        bad = frame[col].ne("") & frame[col + "_num"].isna() & ~nonfinite
        for _, row in frame.loc[bad].iterrows():
            issue(row, col, None, "INVALID_NUMBER", "error", "manual_review")
        if col != "years_inactive":
            for _, row in frame.loc[frame[col].eq("")].iterrows():
                issue(row, col, None, "MISSING_NUMBER", "error", "manual_review")

    frame["years_inactive_missing"] = frame["years_inactive"].eq("")
    for _, row in frame.loc[frame["years_inactive_missing"]].iterrows():
        issue(row, "years_inactive", None, "MISSING_INACTIVITY", "warning", "left_unknown")

    frame["health_clean"] = frame["sfdc_health_score"].where(
        frame["sfdc_health_score"].isin(["Green", "Yellow", "Red"])
    )
    for _, row in frame.loc[frame["health_clean"].isna()].iterrows():
        issue(row, "sfdc_health_score", None, "UNKNOWN_HEALTH", "warning", "left_unknown")

    frame["partner_managed_clean"] = frame["partner_managed"].map(
        {"1.0": 1, "1": 1, "0.0": 0, "0": 0}
    )
    for _, row in frame.loc[frame["partner_managed_clean"].isna()].iterrows():
        issue(row, "partner_managed", None, "UNRESOLVED_PARTNER", "warning", "left_unknown")

    frame["ticket_sentinel"] = frame["open_support_tickets_num"].eq(999)
    frame["tickets_clean"] = frame["open_support_tickets_num"].mask(frame["ticket_sentinel"])
    for _, row in frame.loc[frame["ticket_sentinel"]].iterrows():
        issue(row, "open_support_tickets", None, "TICKET_SENTINEL_999", "warning", "left_unknown")

    checks = {
        "historical_spend_usd": frame["historical_spend_usd_num"].lt(0),
        "discount_tier_pct": frame["discount_tier_pct_num"].notna()
        & ~frame["discount_tier_pct_num"].between(0, 1),
        "monthly_usage_gb": frame["monthly_usage_gb_num"].lt(0),
        "open_support_tickets": frame["open_support_tickets_num"].lt(0),
        "years_inactive": frame["years_inactive_num"].lt(0),
    }
    for col, mask in checks.items():
        for _, row in frame.loc[mask.fillna(False)].iterrows():
            issue(row, col, None, "OUT_OF_RANGE", "error", "manual_review")

    for col in ("account_id", "parent_account_id"):
        frame[col + "_key"] = frame[col].str.strip()
    for _, row in frame.loc[frame["account_id_key"].eq("")].iterrows():
        issue(row, "account_id", None, "MISSING_ACCOUNT_ID", "error", "manual_review")
    dup = frame["account_id_key"].ne("") & frame["account_id_key"].duplicated(keep=False)
    for _, row in frame.loc[dup].iterrows():
        issue(row, "account_id", None, "DUPLICATE_ACCOUNT_ID", "error", "manual_review")

    frame["calendar_inactive_days"] = (
        pd.Timestamp(as_of) - frame["last_booking_date_parsed"]
    ).dt.days
    frame["calendar_inactive_years_approx"] = frame["calendar_inactive_days"] / 365.2425
    frame["inactivity_year_gap_approx"] = (
        frame["calendar_inactive_years_approx"] - frame["years_inactive_num"]
    )
    # Six months is a review threshold for magnitude, separate from eligibility.
    frame["inactivity_value_mismatch"] = frame["inactivity_year_gap_approx"].abs().ge(0.5)
    for _, row in frame.loc[frame["inactivity_value_mismatch"]].iterrows():
        issue(
            row,
            "years_inactive",
            None,
            "INACTIVITY_VALUE_GAP_6M",
            "warning",
            "manual_review",
            row["calendar_inactive_years_approx"],
        )
    frame["calendar_2y_proxy_eligible"] = calendar_2y_proxy(
        frame["last_booking_date_parsed"], as_of
    )
    frame["reported_2y_eligible"] = frame["years_inactive_num"].ge(2).astype("boolean")
    frame.loc[frame["years_inactive_num"].isna(), "reported_2y_eligible"] = pd.NA
    calendar = frame["calendar_2y_proxy_eligible"]
    reported = frame["reported_2y_eligible"]
    known = calendar.notna() & reported.notna()
    frame["eligibility_comparison_status"] = "unknown"
    frame.loc[
        (known & calendar.eq(True) & reported.eq(True)).fillna(False),
        "eligibility_comparison_status",
    ] = "agree_eligible"
    frame.loc[
        (known & calendar.eq(False) & reported.eq(False)).fillna(False),
        "eligibility_comparison_status",
    ] = "agree_ineligible"
    frame.loc[(known & calendar.ne(reported)).fillna(False), "eligibility_comparison_status"] = (
        "disagree"
    )
    frame["eligibility_disagrees"] = frame["eligibility_comparison_status"].eq("disagree")
    for _, row in frame.loc[frame["eligibility_disagrees"]].iterrows():
        issue(
            row,
            "years_inactive",
            None,
            "INACTIVITY_CONTRADICTION",
            "warning",
            "manual_review",
            row["calendar_inactive_years_approx"],
        )
    for _, row in frame.loc[frame["calendar_inactive_days"].lt(0).fillna(False)].iterrows():
        issue(row, "last_booking_date", None, "FUTURE_BOOKING", "error", "manual_review")
    for _, row in frame.loc[
        frame["contract_start_date_parsed"].gt(frame["last_booking_date_parsed"]).fillna(False)
    ].iterrows():
        issue(row, "contract_start_date", None, "CONTRACT_AFTER_BOOKING", "error", "manual_review")

    exceptions = pd.DataFrame(issues, columns=EXCEPTION_COLUMNS)
    return frame, exceptions


def eligibility_reconciliation(frame: pd.DataFrame) -> pd.DataFrame:
    """Disjoint source-report versus calendar-proxy cross-tab; unknown stays unknown."""

    def label(value: object) -> str:
        if pd.isna(value):
            return "unknown"
        return "eligible" if value else "ineligible"

    table = (
        frame.assign(
            calendar_2y_proxy=frame["calendar_2y_proxy_eligible"].map(label),
            source_reported_2y=frame["reported_2y_eligible"].map(label),
        )
        .groupby(["calendar_2y_proxy", "source_reported_2y"], dropna=False)
        .agg(
            account_rows=("account_id", "size"),
            recorded_spend_usd=("historical_spend_usd_num", "sum"),
        )
        .reset_index()
    )
    return table.sort_values(["calendar_2y_proxy", "source_reported_2y"]).reset_index(drop=True)
