CREATE OR REPLACE VIEW flights.web_avg_delay_al_today as
SELECT
    airline_name,
    AVG(CASE
        WHEN runway_delay_secs > 1800 THEN (runway_delay_secs + departure_delay_secs)
        ELSE departure_delay_secs END) as average_delay
FROM flights.airlines_tracked
WHERE dt = (SELECT MAX(dt) FROM flights.airlines_tracked)
GROUP BY airline_name
ORDER BY average_delay DESC

