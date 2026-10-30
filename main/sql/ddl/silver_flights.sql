CREATE EXTERNAL TABLE flights.silver_flights (
    dt                      string,
    fa_flight_id            string,
    airline_code            string,
    flight_number           string,
    code_icao               string,
    scheduled_out           timestamp,
    actual_out              timestamp,
    actual_off              timestamp,
    departure_delay         int,
    runway_delay            int
)
PARTITIONED BY (airport string, year int, month int, day int)
STORED as PARQUET

LOCATION 's3://brendan-silver-flights/clean/flightaware/'
TBLPROPERTIES (
    'projection.enabled'        = 'true',
    'projection.airport.type'   = 'enum',
    'projection.airport.values' = 'KSAN',
    'projection.year.type'      = 'integer',
    'projection.year.range'     = '2026,2030',
    'projection.month.type'     = 'integer',
    'projection.month.range'    = '1,12',
    'projection.month.digits'   = '2',
    'projection.day.type'       = 'integer',
    'projection.day.range'      = '1,31',
    'projection.day.digits'     = '2',
    'storage.location.template' = 
    's3://brendan-silver-flights/clean/flightaware/airport=${airport}/year=${year}/month=${month}/day=${day}/'
)