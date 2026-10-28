import os
import sys
from datetime import datetime, UTC
import pytest
import transformations
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType, TimestampType, IntegerType
from pyspark.sql import SparkSession

@pytest.fixture(scope="session")
def spark():
    '''
    Local spark session for mock data frames
    '''
    os.environ["PYSPARK_PYTHON"] = sys.executable

    session = (
        SparkSession.builder
        .master("local[1]")
        .appName("tests")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "1")
        .getOrCreate()
    )
    yield session
    session.stop()

    

def test_yesterday():
    '''
    Testing for format.
    '''

    yesterday = transformations.yesterday()

    assert len(yesterday) == 10
    assert datetime.strptime(yesterday, "%Y-%m-%d")

def test_parse_timestamps(spark):
    '''
    Using mock dataframe to test if strings for timestamp columns
    are converted correctly.
    '''
    cols = ["scheduled_out", "actual_out", "actual_off", "_ingested_at"]

    schema = StructType(
        [StructField("fa_flight_id", StringType())]
        + [StructField(c, StringType()) for c in cols]
    )

    # using actual_off as null check
    df = spark.createDataFrame(
        [("FLT1", "2026-01-01T07:00:00Z", "2026-01-01T07:10:00Z", None,
          "2026-01-02T07:01:00.12345+00:00")],
        schema
    )

    mock_df = transformations.parse_timestamps(df)

    types = {field.name: field.dataType for field in mock_df.schema.fields}
    for c in cols:
        assert types[c] == TimestampType()

def test_dedupe_flights(spark):
    '''
    Using mock dataframe with duplicates to test if 
    it only keeps the newest rows, drops rows with no fa_flight_id, 
    and removes the helper column.
    '''
    latest = datetime(2026, 1, 1, 7, 1, tzinfo=UTC)
    old = datetime(2026, 1, 1, 7, 0, tzinfo=UTC)

    df = spark.createDataFrame(
        [
            ("2026-10-22", "FLT1", old),    # older duplicate, dropped
            ("2026-10-22", "FLT1", latest), # newer duplicate, kept
            ("2026-10-22", "FLT2", old),    # only copy, kept
            ("2026-10-21", "FLT2", latest), # same flight id on another day, kept
            ("2026-10-22", None, latest)    # no flight id, dropped
        ],
        ["dt", "fa_flight_id", "_ingested_at"]
    )

    mock_df = transformations.dedupe_flights(df)

    assert mock_df.columns == ["dt", "fa_flight_id", "_ingested_at"]

    rows = sorted(
        (r["dt"], r["fa_flight_id"], r["_ingested_at"])
        for r in mock_df.select(
            "dt", "fa_flight_id",
            F.date_format("_ingested_at", "yyyy-MM-dd HH:mm:ss").alias("_ingested_at")
        ).collect()
    )
    assert rows == [
        ("2026-10-21", "FLT2", latest.strftime("%Y-%m-%d %H:%M:%S")),
        ("2026-10-22", "FLT1", latest.strftime("%Y-%m-%d %H:%M:%S")),
        ("2026-10-22", "FLT2", old.strftime("%Y-%m-%d %H:%M:%S"))
    ]

def test_split_ident(spark):
    '''
    Using mock dataframe to test if ident_icao is split into
    airline_code (letters) and flight_number (digits), and
    missing parts become null instead of "".
    '''
    df = spark.createDataFrame(
        [
            ("FLT1", "SWA1234"),  # normal
            ("FLT2", "UAL58932"), # long flight number
            ("FLT3", "SWA"),      # only flight code
            ("FLT4", None)        # no ident -> null
        ],
        ["fa_flight_id", "ident_icao"]
    )

    mock_df = transformations.split_ident(df)

    assert mock_df.columns == [
        "fa_flight_id", "ident_icao", "airline_code", "flight_number"
        ]

    rows = sorted(
        (r["fa_flight_id"], r["airline_code"], r["flight_number"])
        for r in mock_df.collect()
    )
    assert rows == [
        ("FLT1", "SWA", "1234"),
        ("FLT2", "UAL", "58932"),
        ("FLT3", "SWA", None),
        ("FLT4", None, None)
    ]

def test_add_runway_delay(spark):
    '''
    Using mock dataframe to test if runway delay is the seconds between
    actual_out and actual_off, formatted HH:MM:SS, and negative or
    missing times become null.
    '''
    leave_gate = datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC)

    df = spark.createDataFrame(
        [
            ("FLT1", leave_gate, datetime(2026, 1, 1, 14, 12, 32, tzinfo=UTC)),  # normal, 752s
            ("FLT2", leave_gate, datetime(2026, 1, 1, 15, 12, 5, tzinfo=UTC)),   # over an hour
            ("FLT3", leave_gate, leave_gate),                                    # no time
            ("FLT4", leave_gate, datetime(2026, 1, 1, 13, 55, 0, tzinfo=UTC)),   # takeoff time < gate time -> null
            ("FLT5", leave_gate, None)                                           # No takeoff time -> null
        ],
        ["fa_flight_id", "actual_out", "actual_off"]
    )

    mock_df = transformations.add_runway_delay(df)

    assert mock_df.schema['runway_delay_secs'].dataType == IntegerType()

    assert mock_df.columns == [
        "fa_flight_id", "actual_out", "actual_off", "runway_delay_secs", "runway_delay"
    ]

    rows = sorted(
        (r["fa_flight_id"], r["runway_delay_secs"], r["runway_delay"])
        for r in mock_df.select("fa_flight_id", "runway_delay_secs", "runway_delay").collect()
    )
    assert rows == [
        ("FLT1", 752, "00:12:32"),
        ("FLT2", 4325, "01:12:05"),
        ("FLT3", 0, "00:00:00"),
        ("FLT4", None, None),
        ("FLT5", None, None)
    ]

def test_dep_delay_display(spark):
    '''
    Using mock dataframe to test if departure 
    delay is created and is formatted correctly. 
    dep_delay_secs is in seconds, and missing times become null.
    '''

    df = spark.createDataFrame(
        [
            ("FLT1", 123),  # normal
            ("FLT2", 4567), # over an hour
            ("FLT3", 0),    # No delay
            ("FLT4", -10),  # Out of gate early
            ("FLT5", None)  # No delay recorded
        ],
        ["fa_flight_id", "departure_delay"]
    )

    mock_df = transformations.dep_delay_display(df)

    assert mock_df.columns == [
        "fa_flight_id", "departure_delay_secs", "departure_delay"
    ]

    rows = sorted(
        (r["fa_flight_id"], r["departure_delay_secs"], r["departure_delay"])
        for r in mock_df.select("fa_flight_id", "departure_delay_secs", "departure_delay").collect()
    )
    assert rows == [
        ("FLT1", 123, "00:02:03"),
        ("FLT2", 4567, "01:16:07"),
        ("FLT3", 0, "00:00:00"),
        ("FLT4", -10, "-00:00:10"),
        ("FLT5", None, None)
    ]

def test_pst_time(spark):
    '''
    Using mock dataframe to test if UTC timestamps are shifted to
    Pacific time, including when the time changes in the winter.
    '''

    cols = ["scheduled_out", "actual_out", "actual_off"]

    cases = [
        ("FLT1", datetime(2026, 7, 1, 14, 0, tzinfo=UTC)),  # summer
        ("FLT2", datetime(2026, 1, 1, 14, 0, tzinfo=UTC)),  # winter
        ("FLT3", None),                                     # null stays null
    ]
    
    df = spark.createDataFrame(
        [(flight, *[ts] * len(cols)) for flight, ts in cases],
        ["fa_flight_id", *cols],
    )

    mock_df = transformations.pst_time(df)

    rows = {
        r["fa_flight_id"]: r
        for r in mock_df.select(
            "fa_flight_id",
            *[F.date_format(c, "yyyy-MM-dd HH:mm:ss").alias(c) for c in cols],
        ).collect()
    }

    expected = {
        "FLT1": "2026-07-01 07:00:00",
        "FLT2": "2026-01-01 06:00:00",
        "FLT3": None
    }

    for flight, value in expected.items():
        for c in cols:
            assert rows[flight][c] == value, f"{flight} {c}"

def test_clean_flights(spark):
    '''
    Using a mock raw dataframe of two flights (one late, one early)
    to test if clean_flights returns the expected columns and values.
    '''
    # Raw input matches what main() passes in: RAW_SCHEMA plus dt from the file name
    schema = StructType([
        StructField("dt", StringType()),
        StructField("fa_flight_id", StringType()),
        StructField("ident_icao", StringType()),
        StructField("destination", StructType(
            [StructField("code_icao", StringType())]
            )),
        StructField("departure_delay", IntegerType()),
        StructField("scheduled_out", StringType()),
        StructField("actual_out", StringType()),
        StructField("actual_off", StringType()),
        StructField("_ingested_at", StringType())
    ])

    df = spark.createDataFrame(
        [
            # Late: 5 min departure delay, 12:32 runway delay
            ("2026-07-01", "FLT1", "SWA1234", ("KLAX",), 300,
             "2026-07-01T14:00:00Z", 
             "2026-07-01T14:05:00Z", 
             "2026-07-01T14:17:32Z",
             "2026-07-02T07:01:00+00:00"),
            # Early: left the gate 10 secs early, 20:10 runway delay
            ("2026-07-01", "FLT2", "UAL567", ("KSFO",), -10,
             "2026-07-01T16:00:00Z", 
             "2026-07-01T15:59:50Z", 
             "2026-07-01T16:20:00Z",
             "2026-07-02T07:01:00+00:00")
        ],
        schema,
    )

    mock_df = transformations.clean_flights(df)

    assert mock_df.columns == [
        "dt", "fa_flight_id", "airline_code", "flight_number", 
        "code_icao", "scheduled_out", "actual_out", "actual_off",
        "departure_delay_secs", "departure_delay", "runway_delay_secs", "runway_delay"
    ]

    # Formatting UTC in Spark
    fmt = "yyyy-MM-dd HH:mm:ss"
    rows = sorted(
        tuple(r)
        for r in mock_df.select(
            *[F.date_format(c, fmt).alias(c) if c in transformations.TIMESTAMP_COLS else c
              for c in mock_df.columns]
        ).collect()
    )
    assert rows == [
        ("2026-07-01", "FLT1", "SWA", "1234", "KLAX",
         "2026-07-01 07:00:00", "2026-07-01 07:05:00", "2026-07-01 07:17:32",
         300, "00:05:00", 752, "00:12:32"),
        ("2026-07-01", "FLT2", "UAL", "567", "KSFO",
         "2026-07-01 09:00:00", "2026-07-01 08:59:50", "2026-07-01 09:20:00",
         -10, "-00:00:10", 1210, "00:20:10"),
    ]

def test_add_date_parts(spark):
    df = spark.createDataFrame(
        [
            ("2026-01-01",), 
            ("2026-12-31",)
        ],
        ["dt"]
    )

    mock_df = transformations.add_date_parts(df)

    rows = [tuple(r) for r in mock_df.select("year", "month", "day").collect()]

    assert rows== [
        ("2026", "01", "01"),
        ("2026", "12", "31"),
    ]

