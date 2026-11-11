CREATE OR REPLACE VIEW flights.web_avg_delay_al_yesterday as
with filtered_tds as (
    SELECT airline_name,
    -- negative delay is treated as 0/on-time,
    -- no deflated average for leaving early
        CAST(ROUND(AVG(CASE
            WHEN total_delay_secs < 0 THEN 0 
            ELSE total_delay_secs END)) as INT) as average_delay_secs,
        COUNT(total_delay_secs) as num_flights
    FROM flights.airlines_tracked
    WHERE dt = date(current_timestamp AT TIME ZONE 'America/Los_Angeles') - interval '1' day
    -- delays over 10 hours are excluded,
    -- no inflated average for outliers
    AND total_delay_secs < 36000
    GROUP BY airline_name
)

SELECT airline_name,
    num_flights,
    CAST(average_delay_secs / 3600 as INT) as avg_delay_hours,
    CAST(average_delay_secs % 3600 / 60 as INT) as avg_delay_minutes,
    CAST(average_delay_secs % 60 as INT) as avg_delay_secs
FROM filtered_tds
ORDER BY average_delay_secs DESC

