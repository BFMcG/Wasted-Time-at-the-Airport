CREATE TABLE flights.silver_flights (
    dt                date,
    fa_flight_id      string,
    airline_code      string,
    flight_number     string,
    code_icao         string,
    scheduled_out     timestamp,
    scheduled_off     timestamp,
    actual_out        timestamp,
    actual_off        timestamp,
    departure_delay   int,
    runway_delay      int
)
PARTITIONED BY (day(dt))
LOCATION 's3://brendan-silver-flights/iceberg/silver_flights/'
TBLPROPERTIES (
    'table_type'        = 'ICEBERG',
    'format'            = 'parquet',
    'write_compression' = 'zstd'
)