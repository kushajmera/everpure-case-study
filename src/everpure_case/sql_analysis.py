"""Run documented DuckDB queries against the same cleaned account grain."""

from pathlib import Path

import duckdb
import pandas as pd

QUERY_FILES = {
    "spend_concentration": "spend_concentration.sql",
    "regional_spend": "regional_spend.sql",
    "window_analytics": "window_analytics.sql",
    "account_opportunity": "account_opportunity.sql",
}


def run_queries(
    accounts: pd.DataFrame, hierarchy: pd.DataFrame, sql_dir: str | Path
) -> dict[str, pd.DataFrame]:
    """Run every current-data query; longitudinal template is deliberately excluded."""
    connection = duckdb.connect(":memory:")
    try:
        connection.register("accounts", accounts)
        connection.register("hierarchy", hierarchy)
        return {
            name: connection.execute((Path(sql_dir) / filename).read_text(encoding="utf-8")).df()
            for name, filename in QUERY_FILES.items()
        }
    finally:
        connection.close()
