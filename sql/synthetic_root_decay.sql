-- SYNTHETIC METHODOLOGY DEMONSTRATION — NOT OBSERVED EVERPURE REVENUE
-- The synthetic fixture alone assumes root's own revenue excludes its children.
-- execute_synthetic_demo validates the complete, consecutive fiscal calendar before SQL runs.
WITH member_count AS (
    SELECT root_account_id, COUNT(*) AS expected_account_count
    FROM synthetic_hierarchy GROUP BY root_account_id
), observed AS (
    SELECT h.root_account_id, p.fiscal_period_index,
           COUNT(*) AS observed_account_count,
           SUM(p.period_revenue_usd) AS observed_partial_revenue_usd
    FROM synthetic_revenue p
    JOIN synthetic_hierarchy h USING (account_id)
    GROUP BY h.root_account_id, p.fiscal_period_index
), grid AS (
    SELECT m.root_account_id, c.fiscal_period_index, c.fiscal_period_end,
           m.expected_account_count,
           COALESCE(o.observed_account_count, 0) AS observed_account_count,
           o.observed_partial_revenue_usd,
           COALESCE(o.observed_account_count, 0) = m.expected_account_count AS period_complete,
           CASE WHEN o.observed_account_count = m.expected_account_count
                THEN o.observed_partial_revenue_usd END AS root_revenue_usd
    FROM member_count m CROSS JOIN synthetic_calendar c
    LEFT JOIN observed o
      ON m.root_account_id = o.root_account_id
     AND c.fiscal_period_index = o.fiscal_period_index
), sequenced AS (
    SELECT *,
           LAG(root_revenue_usd) OVER root_sequence AS previous_root_revenue_usd,
           LAG(period_complete) OVER root_sequence AS previous_period_complete,
           LEAD(root_revenue_usd) OVER root_sequence AS next_root_revenue_usd,
           DENSE_RANK() OVER (
               PARTITION BY fiscal_period_index ORDER BY root_revenue_usd DESC NULLS LAST
           ) AS unmasked_period_spend_rank
    FROM grid
    WINDOW root_sequence AS (PARTITION BY root_account_id ORDER BY fiscal_period_index)
)
SELECT 'SYNTHETIC METHODOLOGY DEMONSTRATION — NOT OBSERVED EVERPURE REVENUE'
           AS demonstration_label,
       root_account_id, fiscal_period_index, fiscal_period_end,
       expected_account_count, observed_account_count, period_complete,
       observed_partial_revenue_usd, root_revenue_usd,
       previous_root_revenue_usd, next_root_revenue_usd,
       CASE WHEN period_complete THEN unmasked_period_spend_rank END
           AS complete_root_spend_rank,
       CASE WHEN period_complete AND previous_period_complete
            THEN root_revenue_usd - previous_root_revenue_usd END
           AS consecutive_absolute_change_usd,
       CASE WHEN period_complete AND previous_period_complete
                 AND previous_root_revenue_usd <> 0
            THEN (root_revenue_usd - previous_root_revenue_usd)
                 / NULLIF(previous_root_revenue_usd, 0) END
           AS consecutive_pct_change,
       CASE WHEN period_complete AND previous_period_complete
            THEN root_revenue_usd - previous_root_revenue_usd END
           AS signed_change_usd_per_period,
       CASE WHEN NOT period_complete THEN 'incomplete_current_period'
            WHEN previous_period_complete IS NULL THEN 'first_period'
            WHEN NOT previous_period_complete THEN 'incomplete_previous_period'
            WHEN previous_root_revenue_usd = 0 THEN 'consecutive_zero_baseline'
            ELSE 'consecutive' END AS comparison_status
FROM sequenced ORDER BY root_account_id, fiscal_period_index;
