-- Additive recorded-spend proxy, not consolidated revenue or recoverable ARR.
WITH account_spend AS (
    SELECT h.root_account_id, a.account_id, a.historical_spend_usd_num AS spend_usd
    FROM accounts a JOIN hierarchy h USING (source_row_number)
    WHERE h.hierarchy_status = 'resolved'
), root_spend AS (
    SELECT root_account_id, COUNT(*) AS account_count,
           SUM(spend_usd) AS additive_recorded_spend_usd
    FROM account_spend GROUP BY root_account_id
), ranked AS (
    SELECT *, DENSE_RANK() OVER (ORDER BY additive_recorded_spend_usd DESC) AS spend_rank,
           SUM(additive_recorded_spend_usd) OVER () AS all_resolved_spend_usd,
           SUM(additive_recorded_spend_usd) OVER (
               ORDER BY additive_recorded_spend_usd DESC, root_account_id
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
           ) AS cumulative_recorded_spend_usd
    FROM root_spend
)
SELECT *, additive_recorded_spend_usd / NULLIF(all_resolved_spend_usd, 0) AS spend_share,
       cumulative_recorded_spend_usd / NULLIF(all_resolved_spend_usd, 0) AS cumulative_share,
       additive_recorded_spend_usd / NULLIF(account_count, 0)
           AS mean_recorded_spend_per_account_usd
FROM ranked ORDER BY spend_rank, root_account_id;
