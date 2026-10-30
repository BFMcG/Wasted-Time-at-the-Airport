CREATE OR REPLACE VIEW flights.web_pct_delays_today as
SELECT airline_name,
    ROUND(100.0 * CAST(
    SUM(CASE WHEN total_delay_secs >= 900 THEN 1 ELSE 0 END)
    AS DOUBLE) / COUNT(total_delay_secs), 2) as pct_of_flights_delayed
FROM flights.airlines_tracked
WHERE dt = (SELECT MAX(dt) FROM flights.airlines_tracked)
GROUP BY airline_name
ORDER BY pct_of_flights_delayed DESC