-- Account-native region: each source row contributes to exactly one region.
WITH regional AS (
    SELECT COALESCE(region_clean, 'UNKNOWN') AS region,
           COUNT(*) AS account_count,
           SUM(historical_spend_usd_num) AS recorded_spend_usd
    FROM accounts GROUP BY 1
), ranked AS (
    SELECT *, DENSE_RANK() OVER (ORDER BY recorded_spend_usd DESC) AS region_spend_rank,
           SUM(recorded_spend_usd) OVER () AS all_recorded_spend_usd
    FROM regional
)
SELECT *, recorded_spend_usd / NULLIF(all_recorded_spend_usd, 0) AS spend_share,
       recorded_spend_usd / NULLIF(account_count, 0) AS mean_recorded_spend_per_account_usd
FROM ranked ORDER BY region_spend_rank, region;
