CREATE OR REPLACE VIEW flights.web_top_delays_month as
SELECT CAST(dt as VARCHAR(10)) as dt, airline_code, flight_number, airline_name,
    CAST(total_delay_secs / 3600 as INT) as delay_hours,
    CAST(total_delay_secs % 3600 / 60 as INT) as delay_minutes,
    total_delay_secs
FROM flights.airlines_tracked
WHERE dt >= date_trunc('month', 
    date(current_timestamp AT TIME ZONE 'America/Los_Angeles') - interval '1' day)
ORDER BY total_delay_secs DESC
LIMIT 10