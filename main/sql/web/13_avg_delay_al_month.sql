CREATE OR REPLACE VIEW flights.web_avg_delay_al_today as
SELECT
    dt,
    airline_name,
    ROUND(AVG(CASE
        WHEN runway_delay > 1800 THEN (runway_delay + departure_delay)
        ELSE departure_delay END), 1) as average_delay
FROM flights.airlines_tracked
WHERE year * 100 + month = (SELECT MAX(year * 100 + month) FROM flights.airlines_tracked)
GROUP BY airline_name
ORDER BY average_delay DESC