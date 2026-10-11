"""Stable Phase 1 source contract and analysis controls."""

from datetime import date
from pathlib import Path

SOURCE_COLUMNS = (
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
)
DEFAULT_AS_OF = date(2026, 10, 9)
SOURCE_RELATIVE_PATH = Path("data/raw/Case_Study_1_Install_Base_Reactivation.csv")
OUTPUT_RELATIVE_PATH = Path("outputs/phase1")
REGION_MAP = {
    "amer - us east": "AMER - US East",
    "amer - us west": "AMER - US West",
    "apac - japan": "APAC - Japan",
    "emea - france": "EMEA - France",
    "emea - germany": "EMEA - Germany",
}
