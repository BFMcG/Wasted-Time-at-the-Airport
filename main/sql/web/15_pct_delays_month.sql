CREATE OR REPLACE VIEW flights.web_pct_delays_month as
SELECT airline_name,
    ROUND(100.0 * CAST(
    SUM(CASE WHEN total_delay_secs >= 900 THEN 1 ELSE 0 END)
    AS DOUBLE) / COUNT(total_delay_secs), 2) as pct_of_flights_delayed,
    COUNT(total_delay_secs) as num_flights
FROM flights.airlines_tracked
WHERE year = year(date(current_timestamp AT TIME ZONE 'America/Los_Angeles') - interval '1' day)
AND month = month(date(current_timestamp AT TIME ZONE 'America/Los_Angeles') - interval '1' day)
GROUP BY airline_name
ORDER BY pct_of_flights_delayed DESC