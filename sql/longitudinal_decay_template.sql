-- TEMPLATE ONLY. Required input table does not exist in the supplied CSV.
-- Required grain: one account_id + closed fiscal_period_index per period.
-- Required columns: account_id TEXT, fiscal_period_index INTEGER,
-- fiscal_period_end DATE, booked_revenue_usd DECIMAL, with a complete indexed
-- fiscal calendar, consistent revenue definition and consolidation rules.
-- Missing period rows are NOT zero; the index exposes gaps. Do not execute on
-- the supplied one-row-per-account CSV. The executed synthetic demonstration
-- is in synthetic_account_decay.sql and synthetic_root_decay.sql.
WITH period_revenue AS (
    SELECT account_id, fiscal_period_index, fiscal_period_end,
           SUM(booked_revenue_usd) AS period_revenue_usd
    FROM account_period_revenue
    GROUP BY account_id, fiscal_period_index, fiscal_period_end
), account_path AS (
    SELECT *,
        LAG(fiscal_period_index) OVER (
            PARTITION BY account_id ORDER BY fiscal_period_index
        ) AS previous_period_index,
        LAG(period_revenue_usd) OVER (
            PARTITION BY account_id ORDER BY fiscal_period_index
        ) AS previous_period_revenue_usd,
        LEAD(period_revenue_usd) OVER (
            PARTITION BY account_id ORDER BY fiscal_period_index
        ) AS next_period_revenue_usd
    FROM period_revenue
)
SELECT *, fiscal_period_index - previous_period_index AS elapsed_periods,
       CASE WHEN previous_period_index IS NOT NULL
            THEN period_revenue_usd - previous_period_revenue_usd END
           AS across_observation_absolute_change_usd,
       CASE WHEN fiscal_period_index - previous_period_index = 1
                 AND previous_period_revenue_usd <> 0
            THEN (period_revenue_usd - previous_period_revenue_usd)
                 / NULLIF(previous_period_revenue_usd, 0) END
           AS consecutive_pct_change,
       CASE WHEN previous_period_index IS NOT NULL
            THEN (period_revenue_usd - previous_period_revenue_usd)
                 / NULLIF(fiscal_period_index - previous_period_index, 0)
            END AS signed_change_usd_per_period,
       CASE WHEN previous_period_index IS NULL THEN 'first_observation'
            WHEN fiscal_period_index - previous_period_index > 1 THEN 'nonconsecutive_gap'
            WHEN previous_period_revenue_usd = 0 THEN 'consecutive_zero_baseline'
            ELSE 'consecutive' END AS comparison_status
FROM account_path ORDER BY account_id, fiscal_period_index;
