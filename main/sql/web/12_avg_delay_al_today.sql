CREATE OR REPLACE VIEW flights.web_avg_delay_al_today as
with ads as (SELECT
    airline_name,
    CAST(ROUND(AVG(CASE
        WHEN runway_delay > 1800 THEN (runway_delay + departure_delay)
        ELSE departure_delay END)) as INT) as average_delay_secs
FROM flights.airlines_tracked
WHERE dt = (SELECT MAX(dt) FROM flights.airlines_tracked)
GROUP BY airline_name)

SELECT airline_name,
    CAST(average_delay_secs / 3600 as INT) as average_delay_hours,
    CAST(average_delay_secs % 3600 / 60 as INT) as average_delay_minutes,
    average_delay_secs
FROM ads
ORDER BY average_delay_secs DESC

