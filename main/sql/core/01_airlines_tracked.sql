CREATE OR REPLACE VIEW flights.airlines_tracked AS
SELECT s.*, a.airline_name,
CASE
    WHEN s.runway_delay > 1800 THEN s.departure_delay + (s.runway_delay - 1800)
    ELSE s.departure_delay END as total_delay_secs
FROM flights.silver_flights s
JOIN flights.airlines a
ON s.airline_code = a.airline_code