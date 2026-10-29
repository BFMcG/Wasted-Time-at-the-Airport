CREATE OR REPLACE VIEW flights.web_top_delays_month as
SELECT dt, airline_code, flight_number, airline_name,
    CASE
        WHEN runway_delay > 1800 THEN (runway_delay + departure_delay)
        ELSE departure_delay END as total_delay
FROM flights.airlines_tracked
WHERE year * 100 + month = (SELECT MAX(year * 100 + month) FROM flights.airlines_tracked)
ORDER BY total_delay DESC
LIMIT 10