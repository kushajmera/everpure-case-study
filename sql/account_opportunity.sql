-- Descriptive features only. Ranking is recorded spend, not predicted opportunity.
WITH features AS (
    SELECT a.account_id, h.root_account_id, a.region_clean AS region,
           a.historical_spend_usd_num AS recorded_spend_usd,
           a.calendar_inactive_days, a.years_inactive_num AS reported_years_inactive,
           a.calendar_2y_proxy_eligible, a.reported_2y_eligible,
           a.eligibility_comparison_status,
           a.partner_managed_clean, a.health_clean, a.tickets_clean,
           a.monthly_usage_gb_num, a.discount_tier_pct_num,
           h.hierarchy_status
    FROM accounts a JOIN hierarchy h USING (source_row_number)
), ranked AS (
    SELECT *, DENSE_RANK() OVER (
               PARTITION BY region ORDER BY recorded_spend_usd DESC
           ) AS region_recorded_spend_rank,
           CASE WHEN hierarchy_status = 'resolved' THEN DENSE_RANK() OVER (
               PARTITION BY root_account_id ORDER BY recorded_spend_usd DESC
           ) END AS root_recorded_spend_rank
    FROM features
)
SELECT *, partner_managed_clean IS NULL AS ownership_unresolved,
       hierarchy_status <> 'resolved' AS hierarchy_unresolved,
       health_clean IS NULL AS health_unknown,
       tickets_clean IS NULL AS ticket_count_unknown,
       eligibility_comparison_status = 'disagree' AS eligibility_disagrees
FROM ranked ORDER BY recorded_spend_usd DESC NULLS LAST, account_id;
