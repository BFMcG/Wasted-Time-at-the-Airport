import sys
from datetime import UTC, datetime, timedelta

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql.types import (
    IntegerType,
    StringType,
    StructField,
    StructType,
)

AIRPORT = "KSAN"
RAW_PREFIX = "raw/flightaware"
CLEAN_PREFIX = "clean/flightaware"
PST = "America/Los_Angeles"

TIMESTAMP_COLS = ["scheduled_out", "actual_out", "actual_off"]


RAW_SCHEMA = StructType([
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

def yesterday() -> str:
    '''
    Yesterday's date (UTC) in YYYY-MM-DD, matching the key the handler writes.
    '''
    return (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")

def parse_timestamps(df: DataFrame) -> DataFrame:
    '''
    Converting strings into timestamps
    '''
    for c in TIMESTAMP_COLS + ["_ingested_at"]:
        df = df.withColumn(c, F.to_timestamp(c))
    return df

def dedupe_flights(df: DataFrame) -> DataFrame:
    '''
    If there are duplicates keep the most recently ingested row per fa_flight_id.
    '''
    latest_first = Window.partitionBy("dt", "fa_flight_id").orderBy(F.col("_ingested_at").desc())
    return (
        df.filter(F.col("fa_flight_id").isNotNull())
        .withColumn("_rn", F.row_number().over(latest_first))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )

def split_ident(df: DataFrame) -> DataFrame:
    '''
    Splitting ident_icao into flight_number and airline icao code.
    "SWA1234" -> airline_code "SWA", flight_number "1234".
    '''
    airline_code = F.regexp_extract("ident_icao", r"^([A-Z]+)", 1)
    flight_number = F.regexp_extract("ident_icao", r"(\d+)$", 1)
    return (
        df.withColumn("airline_code", F.when(airline_code != "", F.upper(airline_code)))
        .withColumn("flight_number", F.when(flight_number != "", flight_number))
    )

def add_runway_delay(df: DataFrame) -> DataFrame:
    '''
    Seconds between leaving the gate (actual_out) and wheels up (actual_off).
    Negative values become null.
    '''
    seconds = (F.unix_timestamp("actual_off") - F.unix_timestamp("actual_out")).cast("int")

    return df.withColumn(
        "runway_delay", 
        F.when((seconds >= 0) & seconds.isNotNull(), seconds)
        )


def pst_time(df: DataFrame) -> DataFrame:
    '''
    Change from UTC time to PST.
    '''
    for c in TIMESTAMP_COLS:
        df = df.withColumn(c, F.from_utc_timestamp(c, PST))
    return df

def clean_flights(df: DataFrame) -> DataFrame:
    df = dedupe_flights(parse_timestamps(df))
    df = split_ident(df)
    df = add_runway_delay(df)
    df = pst_time(df)

    return df.select(
        "dt",
        "fa_flight_id",
        "airline_code",
        "flight_number",
        F.col("destination.code_icao").alias("code_icao"),
        "scheduled_out",
        "actual_out",
        "actual_off",
        "departure_delay",
        "runway_delay"
    )

def add_date_parts(df: DataFrame) -> DataFrame:
    '''
    Splitting dt into year, month, and day inorder
    for partitioning in the clean S3 bucket
    '''
    return (
        df.withColumn("year", F.substring("dt", 1, 4))
        .withColumn("month", F.substring("dt", 6, 2))
        .withColumn("day", F.substring("dt", 9, 2))
    )

def main():
    from awsglue.context import GlueContext
    from awsglue.job import Job
    from awsglue.utils import getResolvedOptions
    from pyspark.context import SparkContext

    args = getResolvedOptions(sys.argv, ["JOB_NAME", "RAW_BUCKET", "CLEAN_BUCKET"])

    # Backfill option: --START_DATE / --END_DATE, default yesterday
    if "--START_DATE" in sys.argv:
        dates = getResolvedOptions(sys.argv, ["START_DATE", "END_DATE"])
        start_date, end_date = dates["START_DATE"], dates["END_DATE"]
    else:
        start_date = end_date = yesterday()

    glue_context = GlueContext(SparkContext.getOrCreate())
    spark = glue_context.spark_session
    spark.conf.set("spark.sql.session.timeZone", "UTC")

    # Only overwrite dt folders currently being written
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    job = Job(glue_context)
    job.init(args["JOB_NAME"], args)

    src = f"s3://{args['RAW_BUCKET']}/{RAW_PREFIX}/airport={AIRPORT}/departures_*.jsonl.gz"
    dst = f"s3://{args['CLEAN_BUCKET']}/{CLEAN_PREFIX}/airport={AIRPORT}/"

    raw = (spark.read.schema(RAW_SCHEMA).json(src)
           .withColumn("dt", F.regexp_extract(F.input_file_name(), 
            r"departures_(\d{4}-\d{2}-\d{2})", 1))
           .filter(F.col("dt").between(start_date, end_date)))
    clean = clean_flights(raw).cache()

    record_count = clean.count()
    if record_count == 0:
        raise RuntimeError(f"No clean flights produced from {src}")

    # Writing parquet file by year, month, day
    partition_cols = ["year", "month", "day"]

    (add_date_parts(clean)
        .repartition(*partition_cols)
        .write.mode("overwrite")
        .partitionBy(*partition_cols)
        .parquet(dst))

    if "--START_DATE" in sys.argv:
        print(f"Wrote {record_count} flights for {start_date} -> {end_date} to {dst}")
    else:
        print(f"Wrote {record_count} flights to {dst}")

    job.commit()


if __name__ == "__main__":
    main()