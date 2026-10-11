-- SYNTHETIC-DATE / SOURCE-PATTERN DIAGNOSTIC for this CSV.
-- Dates are exactly 2019-01-01 + (numeric account ID - 1000) days.
-- LAG/LEAD compare adjacent ACCOUNT booking dates within a parent group.
-- These gaps collapse to account-ID differences; they are not observed
-- behavioral booking frequency, within-account revenue decay, or ticket velocity.
WITH booked AS (
    SELECT h.root_account_id, a.account_id, a.last_booking_date_parsed AS booking_date,
           a.calendar_inactive_days,
           a.calendar_2y_proxy_eligible
    FROM accounts a JOIN hierarchy h USING (source_row_number)
    WHERE h.hierarchy_status = 'resolved' AND a.last_booking_date_parsed IS NOT NULL
), neighbors AS (
    SELECT *,
        LAG(booking_date) OVER (
            PARTITION BY root_account_id ORDER BY booking_date, account_id
        ) AS previous_account_booking_date,
        LEAD(booking_date) OVER (
            PARTITION BY root_account_id ORDER BY booking_date, account_id
        ) AS next_account_booking_date,
        DENSE_RANK() OVER (
            PARTITION BY root_account_id ORDER BY booking_date DESC
        ) AS recency_rank_within_root,
        MAX(booking_date) OVER (PARTITION BY root_account_id) AS latest_group_booking_date
    FROM booked
)
SELECT *, date_diff('day', previous_account_booking_date, booking_date)
           AS days_since_previous_account_booking,
       date_diff('day', booking_date, next_account_booking_date)
           AS days_until_next_account_booking,
       CASE WHEN calendar_2y_proxy_eligible THEN 'calendar_2y_proxy'
            WHEN calendar_2y_proxy_eligible IS NULL THEN 'unknown'
            ELSE 'under_2_calendar_years' END AS calendar_inactivity_segment
FROM neighbors ORDER BY root_account_id, booking_date, account_id;
