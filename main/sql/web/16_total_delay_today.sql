CREATE OR REPLACE VIEW flights.web_total_delay_today as
with tds as (
    SELECT COUNT(total_delay_secs) as flights_today,
        SUM(CASE WHEN total_delay_secs < 0 
                THEN 0 ELSE total_delay_secs END) as sum_delay_secs
    FROM flights.airlines_tracked
    WHERE dt = (SELECT MAX(dt) FROM flights.airlines_tracked)
)

SELECT flights_today,
    CAST(sum_delay_secs / 3600 as INT) as hours_wasted,
    CAST(sum_delay_secs % 3600 / 60 as INT) as minutes_wasted,
    CAST(sum_delay_secs % 60 as INT) as secs_wasted
FROM tds

