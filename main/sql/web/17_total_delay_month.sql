CREATE OR REPLACE VIEW flights.web_total_delay_month as
with tds as (
    SELECT COUNT(total_delay_secs) as delayed_flights_month,
        SUM(CASE WHEN total_delay_secs < 0 
                THEN 0 ELSE total_delay_secs END) as sum_delay_secs
    FROM flights.airlines_tracked
    WHERE dt >= date_trunc('month', 
        date(current_timestamp AT TIME ZONE 'America/Los_Angeles') - interval '1' day)
    AND total_delay_secs > 0
)

SELECT delayed_flights_month,
    CAST(sum_delay_secs / 86400 as INT)        as days_wasted,
    CAST(sum_delay_secs % 86400 / 3600 as INT) as hours_wasted,
    CAST(sum_delay_secs % 3600 / 60 as INT)    as minutes_wasted,
    CAST(sum_delay_secs % 60 as INT)           as secs_wasted
FROM tds