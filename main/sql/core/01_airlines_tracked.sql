CREATE OR REPLACE VIEW flights.airlines_tracked AS
WITH delays as (SELECT s.*, a.airline_name,
CASE
    WHEN s.departure_delay <= 600 THEN 0
    ELSE s.departure_delay - 600 END as gate_delay,
CASE
    WHEN date_diff('second', s.scheduled_off, s.actual_off) <= 1200 THEN 0
    WHEN s.runway_delay IS NULL
        -- Negates departure_delay, subtracts 20 minute scheduled taxi time.
        -- If the delay comes out to less than 0 
        -- (less than 20 min taxi time/large gate delay) then 0.
        THEN GREATEST(
            date_diff('second', s.scheduled_off, s.actual_off) - s.departure_delay - 1200, 0
            )
    WHEN s.runway_delay <= 1200 THEN 0
    ELSE s.runway_delay - 1200 END as takeoff_delay
FROM flights.silver_flights s
JOIN flights.airlines a
ON s.airline_code = a.airline_code)

SELECT *, 
(gate_delay + takeoff_delay) as total_delay_secs
FROM delays