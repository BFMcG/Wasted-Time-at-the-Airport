CREATE OR REPLACE VIEW flights.departures_tracked AS
SELECT s.*, a.airline_name
FROM flights.silver_flights s
JOIN flights.airlines a
ON s.airline_code = a.airline_code