-- SYNTHETIC METHODOLOGY DEMONSTRATION — NOT OBSERVED EVERPURE REVENUE
-- Revenue is one account-period observation. A missing row is not zero revenue.
WITH validated AS (
    SELECT p.account_id, h.root_account_id, p.fiscal_period_index,
           p.fiscal_period_end, p.period_revenue_usd
    FROM synthetic_revenue p
    JOIN synthetic_hierarchy h USING (account_id)
    JOIN synthetic_calendar c
      ON p.fiscal_period_index = c.fiscal_period_index
     AND p.fiscal_period_end = c.fiscal_period_end
), sequenced AS (
    SELECT *,
           LAG(fiscal_period_index) OVER account_sequence AS previous_period_index,
           LAG(period_revenue_usd) OVER account_sequence AS previous_revenue_usd,
           LEAD(fiscal_period_index) OVER account_sequence AS next_period_index,
           LEAD(period_revenue_usd) OVER account_sequence AS next_revenue_usd,
           DENSE_RANK() OVER (
               PARTITION BY account_id ORDER BY fiscal_period_index DESC
           ) AS observed_period_recency_rank
    FROM validated
    WINDOW account_sequence AS (PARTITION BY account_id ORDER BY fiscal_period_index)
)
SELECT 'SYNTHETIC METHODOLOGY DEMONSTRATION — NOT OBSERVED EVERPURE REVENUE'
           AS demonstration_label,
       account_id, root_account_id, fiscal_period_index, fiscal_period_end,
       period_revenue_usd, previous_period_index, previous_revenue_usd,
       next_period_index, next_revenue_usd, observed_period_recency_rank,
       fiscal_period_index - previous_period_index AS elapsed_periods,
       CASE WHEN previous_period_index IS NOT NULL
            THEN period_revenue_usd - previous_revenue_usd END AS absolute_change_usd,
       CASE WHEN fiscal_period_index - previous_period_index = 1
                 AND previous_revenue_usd <> 0
            THEN (period_revenue_usd - previous_revenue_usd)
                 / NULLIF(previous_revenue_usd, 0) END AS consecutive_pct_change,
       CASE WHEN previous_period_index IS NOT NULL
            THEN (period_revenue_usd - previous_revenue_usd)
                 / NULLIF(fiscal_period_index - previous_period_index, 0)
            END AS signed_change_usd_per_period,
       CASE WHEN previous_period_index IS NULL THEN 'first_observation'
            WHEN fiscal_period_index - previous_period_index > 1 THEN 'nonconsecutive_gap'
            WHEN previous_revenue_usd = 0 THEN 'consecutive_zero_baseline'
            ELSE 'consecutive' END AS comparison_status
FROM sequenced ORDER BY account_id, fiscal_period_index;
