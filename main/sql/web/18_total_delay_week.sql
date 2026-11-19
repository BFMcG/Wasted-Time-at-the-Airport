CREATE OR REPLACE VIEW flights.web_total_delay_week as
with tds as (SELECT dt, 
    SUM(total_delay_secs) as sum_delay_secs
    FROM flights.airlines_tracked
    WHERE dt BETWEEN date(current_timestamp AT TIME ZONE 'America/Los_Angeles') - interval '7' day
        AND date(current_timestamp AT TIME ZONE 'America/Los_Angeles') - interval '1' day
    AND total_delay_secs > 0
    GROUP BY dt)

SELECT CAST(dt as VARCHAR(10)) as dt,
    sum_delay_secs
FROM tds