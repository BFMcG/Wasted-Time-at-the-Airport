CREATE OR REPLACE VIEW flights.web_avg_delay_al_today as
SELECT airline_name,
    -- Double cast, inner for converting avg (float) -> int
    -- outer for converting the number after division (float) -> int
    CAST(CAST(ROUND(AVG(total_delay_secs)) as INT) / 3600 as INT) as average_delay_hours,
    CAST(CAST(ROUND(AVG(total_delay_secs)) as INT) % 3600 / 60 as INT) as average_delay_minutes,
    CAST(ROUND(AVG(total_delay_secs)) as INT) as average_delay_secs
FROM flights.airlines_tracked
WHERE dt = (SELECT MAX(dt) FROM flights.airlines_tracked)
GROUP BY airline_name
ORDER BY average_delay_secs DESC

