import pytest
from pathlib import Path
from pyspark.sql.types import (
    IntegerType,
    StringType,
    StructField,
    StructType,
)


SCHEMA = StructType([
    StructField("dt", StringType()),
    StructField("year", IntegerType()),
    StructField("month", IntegerType()),
    StructField("day", IntegerType()),
    StructField("airline_code", StringType()),
    StructField("flight_number", StringType()),
    StructField("airline_name", StringType()),
    StructField("departure_delay", IntegerType()),
    StructField("runway_delay", IntegerType())
])

# So pytest will run properly from inside test_files/
DIR = Path(__file__).parent.parent / "main" / "sql" / "web"

@pytest.fixture()
def mock_airlines(spark):
    df = spark.createDataFrame(
        [
            # Normal delay: runway_delay <= 1800
            ("2026-01-02", 2026, 1, 2, "UAL", "1234", "United", 3661, 600),
            # Long runway: runway_delay > 1800
            ("2026-01-02", 2026, 1, 2, "UAL", "567", "United", 300, 2400),
            # Zero delay
            ("2026-01-02", 2026, 1, 2, "DAL", "890", "Delta", 0, 0),
            # Large delay
            ("2026-01-02", 2026, 1, 2, "SWA", "321", "Southwest", 64000, 600),
            # Flight from the previous day
            ("2026-01-01", 2026, 1, 1, "SWA", "654", "Southwest", 120, 600),
            # Flight from different year/month/day
            ("2025-12-31", 2025, 12, 31, "UAL", "111", "United", 1200, 100),
            # Negative delay: flight left early
            ("2026-01-02", 2026, 1, 2, "SWA", "222", "Southwest", -120, 100),
            # Null runway_delay
            ("2026-01-02", 2026, 1, 2, "DAL", "3333", "Delta", 1200, None)
        ],
        SCHEMA 
    )

    df.createOrReplaceTempView("airlines_tracked")
    return df

def run_view(spark, sql_file):
    sql = (DIR / sql_file).read_text()
    sql = sql.replace("CREATE OR REPLACE VIEW", "CREATE OR REPLACE TEMP VIEW").replace("flights.", "")
    spark.sql(sql)

@pytest.mark.usefixtures("mock_airlines")
def test_top_delays_today(spark):
    run_view(spark, "10_top_delays_today.sql")

    df = spark.sql(
        '''
        SELECT airline_code, flight_number, airline_name,
        delay_hours, delay_minutes, total_delay_secs
        FROM web_top_delays_today
        '''
    ).collect()

    rows = sorted(
        tuple(r) for r in df
    )

    expected = sorted([
        ("SWA", "321", "Southwest", 17, 46, 64000),
        ("UAL", "1234", "United", 1, 1, 3661),
        ("UAL", "567", "United", 0, 45, 2700),
        ("DAL", "3333", "Delta", 0, 20, 1200),
        ("DAL", "890", "Delta", 0, 0, 0),
        ("SWA", "222", "Southwest", 0, -2, -120)
    ])

    assert rows == expected

@pytest.mark.usefixtures("mock_airlines")
def test_top_delays_month(spark):
    run_view(spark, "11_top_delays_month.sql")

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
        ("2026-01-02", "SWA", "321", "Southwest", 17, 46, 64000),
        ("2026-01-02", "UAL", "1234", "United", 1, 1, 3661),
        ("2026-01-02", "UAL", "567", "United", 0, 45, 2700),
        ("2026-01-02", "DAL", "3333", "Delta", 0, 20, 1200),
        ("2026-01-01", "SWA", "654", "Southwest", 0, 2, 120),
        ("2026-01-02", "DAL", "890", "Delta", 0, 0, 0),
        ("2026-01-02", "SWA", "222", "Southwest", 0, -2, -120)
    ])

    assert rows == expected

@pytest.mark.usefixtures("mock_airlines")
def test_avg_delay_al_today(spark):
    run_view(spark, "12_avg_delay_al_today.sql")

    df = spark.sql(
        '''
        SELECT airline_name, average_delay_hours,
        average_delay_minutes, average_delay_secs
        FROM web_avg_delay_al_today
        '''
    ).collect()

    rows = sorted(
        tuple(r) for r in df
    )

    expected = sorted([
        ("Southwest", 8, 52, 31940),
        ("United", 0, 53, 3181),
        ("Delta", 0, 10, 600)
    ])

    assert rows == expected

@pytest.mark.usefixtures("mock_airlines")
def test_avg_delay_al_month(spark):
    run_view(spark, "13_avg_delay_al_month.sql")

    df = spark.sql(
        '''
        SELECT airline_name, average_delay_hours,
        average_delay_minutes, average_delay_secs
        FROM web_avg_delay_al_month
        '''
    ).collect()

    rows = sorted(
        tuple(r) for r in df
    )

    expected = sorted([
        ("Southwest", 5, 55, 21333),
        ("United", 0, 53, 3181),
        ("Delta", 0, 10, 600)
    ])

    assert rows == expected