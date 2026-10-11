-- One resolved row per source account. Unresolved hierarchy is retained separately.
WITH resolved AS (
    SELECT h.root_account_id, h.account_id, h.hierarchy_depth,
           a.historical_spend_usd_num AS recorded_spend_usd,
           a.region_clean, a.partner_managed_clean
    FROM hierarchy h
    JOIN accounts a USING (source_row_number)
    WHERE h.hierarchy_status = 'resolved'
)
SELECT root_account_id, COUNT(*) AS account_count,
       SUM(CASE WHEN hierarchy_depth = 1 THEN 1 ELSE 0 END) AS direct_child_count,
       MAX(hierarchy_depth) AS max_depth,
       SUM(recorded_spend_usd) AS additive_recorded_spend_usd,
       COUNT(DISTINCT region_clean) AS region_count,
       COUNT(DISTINCT partner_managed_clean) AS known_partner_states
FROM resolved GROUP BY root_account_id ORDER BY root_account_id;
