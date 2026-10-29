CREATE OR REPLACE VIEW flights.web_top_delays_month as
with tds as (SELECT 
    dt, airline_code, flight_number, airline_name,
    CASE
        WHEN runway_delay > 1800 THEN (runway_delay + departure_delay)
        ELSE departure_delay END as total_delay_secs
    FROM flights.airlines_tracked
    WHERE year * 100 + month = 
    (SELECT MAX(year * 100 + month) FROM flights.airlines_tracked))

SELECT dt, airline_code, flight_number, airline_name,
    CAST(total_delay_secs / 3600 as INT) as delay_hours,
    CAST(total_delay_secs % 3600 / 60 as INT) as delay_minutes,
    total_delay_secs
FROM tds
ORDER BY total_delay_secs DESC
LIMIT 10