import pytest
from pathlib import Path
from datetime import datetime, timedelta
from pyspark.sql.types import (
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType
)

###########################################################
#                   IMPORTANT MESSAGE:                    #
###########################################################

# If queires are run between 12:00am and 4:00am (or until
# the pipeline finishes) they will be empty because 
# current_timestamp is being used to filter data, so the
# query will be looking for data that hasn't been ingested yet.



CORE_SCHEMA = StructType([
    StructField("dt", StringType()),
    StructField("airline_code", StringType()),
    StructField("flight_number", StringType()),
    StructField("departure_delay", IntegerType()),
    StructField("runway_delay", IntegerType()),
    StructField("scheduled_off", TimestampType()),
    StructField("actual_off", TimestampType())
])

WEB_SCHEMA = StructType([
    StructField("dt", StringType()),
    StructField("airline_code", StringType()),
    StructField("airline_name", StringType()),
    StructField("flight_number", StringType()),
    StructField("total_delay_secs", IntegerType())
])

# So pytest will run properly from inside test_files/
DIR = Path(__file__).parent.parent / "main" / "sql"

# Query dates from the day before (2026-01-02)
TEST_DATE = "2026-01-03"

def run_view(spark, sql_file):
    sql = (DIR / sql_file).read_text()
    sql = sql.replace("CREATE OR REPLACE VIEW", "CREATE OR REPLACE TEMP VIEW")
    sql = sql.replace("flights.", "")
    sql = sql.replace("date(current_timestamp AT TIME ZONE 'America/Los_Angeles')", f"DATE '{TEST_DATE}'")
    sql = sql.replace("date_diff('second',", "date_diff(second,")
    spark.sql(sql)

@pytest.fixture()
def mock_core_airlines(spark):
    scheduled_off = datetime(2026, 1, 2, 8, 0)
    ontime_off = scheduled_off + timedelta(minutes=20)
    early_off = scheduled_off + timedelta(minutes=10)
    # 30 minute delay sitting on the runway
    late_off = scheduled_off + timedelta(minutes=50)

    df = spark.createDataFrame(
        [
            # Short runway: runway_delay <= 1200
            ("2026-01-02", "UAL", "1234", 600, 600,
             scheduled_off, early_off),
            # Long runway: runway_delay > 1200
            ("2026-01-02", "UAL", "567", 600, 2400,
             scheduled_off, late_off),
            # Short departure: departure_delay <= 600
            ("2026-01-02", "SWA", "321", 120, 1200,
             scheduled_off, late_off),
            # Long departure: departure_delay > 600
            ("2026-01-02", "SWA", "321", 1200, 1200,
             scheduled_off, late_off),
            # Zero departure delay
            ("2026-01-02", "DAL", "890", 0, 1200,
             scheduled_off, ontime_off),
            # Null runway_delay actual - scheduled <= 20
            ("2026-01-02", "DAL", "3333", 600, None,
             scheduled_off, ontime_off),
            # Null runway_delay actual - schecduled > 20
            ("2026-01-02", "DAL", "3333", 600, None,
             scheduled_off, late_off),
            # Negative delay: flight left early
            ("2026-01-02", "SWA", "222", -120, 1200,
             scheduled_off, ontime_off),
            # Unwanted airline
            ("2026-01-02", "XYZ", "4444", 600, 1200,
             scheduled_off, ontime_off)
        ],
        CORE_SCHEMA 
    )

    df.createOrReplaceTempView("silver_flights")
    run_view(spark, "core/00_airlines.sql")
    run_view(spark, "core/01_airlines_tracked.sql")
    return df

@pytest.fixture()
def mock_web_airlines(spark):

    df = spark.createDataFrame(
        [
            # Zero Delay
            ("2026-01-02", "UAL", "United", "1234", 0),
            # Large Delay
            ("2026-01-02", "UAL", "United", "567", 14461),
            # Over 24 hour delay
            ("2026-01-02", "UAL", "United", "999", 90061),
            # Short Delay
            ("2026-01-02", "SWA", "Southwest", "321", 300),
            # Medium Delay
            ("2026-01-02", "DAL", "Delta", "456", 3661),
            # Flight from the previous day
            ("2026-01-01", "SWA", "Southwest", "654", 7261),
            # Flight from only different year
            ("2025-01-02", "DAL", "Delta", "000", 25000),
            # Flight from different year/month/day
            ("2025-12-31", "UAL", "United", "111", 50000),
        ],
        WEB_SCHEMA 
    )

    df.createOrReplaceTempView("airlines_tracked")
    return df

@pytest.mark.usefixtures("mock_core_airlines")
def test_airlines_tracked(spark):
    df = spark.sql(
        '''
        SELECT airline_code, flight_number, 
        airline_name, total_delay_secs
        FROM airlines_tracked
        '''
    ).collect()

    rows = sorted(
        tuple(r) for r in df
    )

    expected = sorted([
        ("UAL", "1234", "United", 0),
        ("UAL", "567", "United", 1200),
        ("SWA", "321", "Southwest", 0),
        ("SWA", "321", "Southwest", 600),
        ("DAL", "890", "Delta", 0),
        ("DAL", "3333", "Delta", 0),
        ("DAL", "3333", "Delta", 1200),
        ("SWA", "222", "Southwest", 0)
    ])

    assert rows == expected

@pytest.mark.usefixtures("mock_web_airlines")
def test_top_delays_yesterday(spark):
    run_view(spark, "web/10_top_delays_yesterday.sql")

    df = spark.sql(
        '''
        SELECT airline_code, flight_number, airline_name,
        delay_hours, delay_minutes, total_delay_secs
        FROM web_top_delays_yesterday
        '''
    ).collect()

    rows = sorted(
        tuple(r) for r in df
    )

    expected = sorted([
        ("UAL", "999", "United", 25, 1, 90061),
        ("UAL", "567", "United", 4, 1, 14461),
        ("DAL", "456", "Delta", 1, 1, 3661),
        ("SWA", "321", "Southwest", 0, 5, 300),
        ("UAL", "1234", "United", 0, 0, 0)
    ])

    assert rows == expected

@pytest.mark.usefixtures("mock_web_airlines")
def test_top_delays_month(spark):
    run_view(spark, "web/11_top_delays_month.sql")

    df = spark.sql(
        '''
        SELECT dt, airline_code, flight_number, airline_name,
        delay_hours, delay_minutes, total_delay_secs
        FROM web_top_delays_month
        '''
    ).collect()

    rows = sorted(
        tuple(r) for r in df
    )

    expected = sorted([
        ("2026-01-02", "UAL", "999", "United", 25, 1, 90061),
        ("2026-01-02", "UAL", "567", "United", 4, 1, 14461),
        ("2026-01-01", "SWA", "654", "Southwest", 2, 1, 7261),
        ("2026-01-02", "DAL", "456", "Delta", 1, 1, 3661),
        ("2026-01-02", "SWA", "321", "Southwest", 0, 5, 300),
        ("2026-01-02", "UAL", "1234", "United", 0, 0, 0)
    ])

    assert rows == expected

@pytest.mark.usefixtures("mock_web_airlines")
def test_avg_delay_al_yesterday(spark):
    run_view(spark, "web/12_avg_delay_al_yesterday.sql")

    df = spark.sql(
        '''
        SELECT airline_name, num_flights, avg_delay_hours,
        avg_delay_minutes, avg_delay_secs
        FROM web_avg_delay_al_yesterday
        '''
    ).collect()

    rows = sorted(
        tuple(r) for r in df
    )

    expected = sorted([
        ("United", 2, 2, 0, 31),
        ("Delta", 1, 1, 1, 1),
        ("Southwest", 1, 0, 5, 0)
    ])

    assert rows == expected

@pytest.mark.usefixtures("mock_web_airlines")
def test_avg_delay_al_month(spark):
    run_view(spark, "web/13_avg_delay_al_month.sql")

    df = spark.sql(
        '''
        SELECT airline_name, num_flights, avg_delay_hours,
        avg_delay_minutes, avg_delay_secs
        FROM web_avg_delay_al_month
        '''
    ).collect()

    rows = sorted(
        tuple(r) for r in df
    )

    expected = sorted([
        ("United", 2, 2, 0, 31),
        ("Southwest", 2, 1, 3, 1),
        ("Delta", 1, 1, 1, 1)
    ])

    assert rows == expected

@pytest.mark.usefixtures("mock_web_airlines")
def test_pct_delay_yesterday(spark):
    run_view(spark, "web/14_pct_delays_yesterday.sql")

    df = spark.sql(
        '''
        SELECT airline_name, 
        pct_of_flights_delayed, num_flights
        FROM web_pct_delays_yesterday
        '''
    ).collect()

    rows = sorted(
        tuple(r) for r in df
    )

    expected = sorted([
        ("Delta", 100.0, 1),
        ("United", 66.67, 3),
        ("Southwest", 0.0, 1)
    ])

    assert rows == expected

@pytest.mark.usefixtures("mock_web_airlines")
def test_pct_delay_month(spark):
    run_view(spark, "web/15_pct_delays_month.sql")

    df = spark.sql(
        '''
        SELECT airline_name, 
        pct_of_flights_delayed, num_flights
        FROM web_pct_delays_month
        '''
    ).collect()

    rows = sorted(
        tuple(r) for r in df
    )

    expected = sorted([
        ("Delta", 100.0, 1),
        ("United", 66.67, 3),
        ("Southwest", 50.0, 2)
    ])

    assert rows == expected

@pytest.mark.usefixtures("mock_web_airlines")
def test_total_delay_yesterday(spark):
    run_view(spark, "web/16_total_delay_yesterday.sql")

    df = spark.sql(
        '''
        SELECT delayed_flights_yesterday, 
        days_wasted, hours_wasted,
        minutes_wasted, secs_wasted
        FROM web_total_delay_yesterday
        '''
    ).collect()

    rows = tuple(df[0])

    expected = (4, 1, 6, 8, 3)

    assert rows == expected

@pytest.mark.usefixtures("mock_web_airlines")
def test_total_delay_month(spark):
    run_view(spark, "web/17_total_delay_month.sql")

    df = spark.sql(
        '''
        SELECT delayed_flights_month, 
        days_wasted, hours_wasted,
        minutes_wasted, secs_wasted
        FROM web_total_delay_month
        '''
    ).collect()

    rows = tuple(df[0])

    expected = (5, 1, 8, 9, 4)

    assert rows == expected