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
PST = "America/Los_Angeles"

TIMESTAMP_COLS = ["scheduled_out", "scheduled_off", "actual_out", "actual_off"]


RAW_SCHEMA = StructType([
    StructField("dt", StringType()),
    StructField("fa_flight_id", StringType()),
    StructField("ident_icao", StringType()),
    StructField("destination", StructType(
        [StructField("code_icao", StringType())]
        )),
    StructField("departure_delay", IntegerType()),
    StructField("scheduled_out", StringType()),
    StructField("scheduled_off", StringType()),
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

def drop_missing_departure(df: DataFrame) -> DataFrame:
    '''
    If there are flights with a missing departure delay they are droppped.
    '''
    return (df.filter(F.col("departure_delay").isNotNull()))

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

def log_dropped_flights(raw: DataFrame, max_rows=20) -> tuple[int, int]:
    '''
    Prints number flights that have null departure_delay before they are dropped 
    and the number of flights that were dropped from dedupe_flights function.
    '''
    deduped = dedupe_flights(parse_timestamps(raw))
    dropped_deduped = raw.count() - deduped.count()
    print(f"Dropped {dropped_deduped} flight(s) that were duplicates or "
          f"null fa_flight_id.")

    null_dd_flights = deduped.filter(F.col("departure_delay").isNull())
    missing = null_dd_flights.count()
    print(f"Dropped {missing} flight(s) with no departure_delay.")
    if missing > 0:
        missing_flights = (null_dd_flights
                            .select("fa_flight_id", "scheduled_out", "actual_out")
                            .limit(max_rows)
                            .collect())
        for flight in missing_flights:
            flight_id = flight["fa_flight_id"]
            so = flight["scheduled_out"]
            ao = flight["actual_out"]
            print(f"Missing departure_delay from flight {flight_id} "
                  f"with scheduled_out {so} UTC, actual_out {ao} UTC.")

    return dropped_deduped, missing

def clean_flights(df: DataFrame) -> DataFrame:
    df = dedupe_flights(parse_timestamps(df))
    df = drop_missing_departure(df)
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
        "scheduled_off",
        "actual_out",
        "actual_off",
        "departure_delay",
        "runway_delay"
    )

def date_types(df: DataFrame) -> DataFrame:
    '''
    Casting date columns to types for Iceberg table
    '''
    df = df.withColumn("dt", F.to_date("dt"))

    for c in TIMESTAMP_COLS:
        df = df.withColumn(c, F.col(c).cast("timestamp_ntz"))

    return df

class IcebergTable:
    '''
    Tells spark how to write a dataframe into
    the iceberg table given the table and database from Athena.
    '''

    def __init__(self, database: str, table: str, file_dst: str):
        self.database = database
        self.table = table
        self.file_dst = file_dst

    def spark_settings(self) -> dict:
        '''
        Creating the spark setting to write the cleaned data
        through the glue catalog. Returned as a dictionary for
        easier testing and less Spark work.
        '''
        prefix = "spark.sql.catalog.glue_catalog"
        return {
            "spark.sql.extensions":
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
            prefix:                   "org.apache.iceberg.spark.SparkCatalog",
            f"{prefix}.catalog-impl": "org.apache.iceberg.aws.glue.GlueCatalog",
            f"{prefix}.io-impl":      "org.apache.iceberg.aws.s3.S3FileIO",
            f"{prefix}.warehouse":    self.file_dst
        }

    @property
    def full_name(self) -> str:
        return f"glue_catalog.{self.database}.{self.table}"

    def overwrite_days(self, df: DataFrame) -> None:
        '''
        Overwrite partions that are currently being written.
        '''
        df.writeTo(self.full_name).overwritePartitions()



def main():
    from awsglue.context import GlueContext
    from awsglue.utils import getResolvedOptions
    from pyspark.context import SparkContext
    from pyspark.conf import SparkConf

    args = getResolvedOptions(sys.argv, ["RAW_BUCKET", "CLEAN_BUCKET"])

    # Backfill option: --START_DATE / --END_DATE, default yesterday
    if "--START_DATE" in sys.argv:
        dates = getResolvedOptions(sys.argv, ["START_DATE", "END_DATE"])
        start_date, end_date = dates["START_DATE"], dates["END_DATE"]
    else:
        start_date = end_date = yesterday()

    # Setting up Athena parameters for IcebergTable 

    dst = f"s3://{args['CLEAN_BUCKET']}/iceberg/"
    src = f"s3://{args['RAW_BUCKET']}/{RAW_PREFIX}/airport={AIRPORT}/departures_*.jsonl.gz"
    

    silver = IcebergTable(
        database="flights",
        table="silver_flights",
        file_dst=dst
    )

    # Configuring Spark settings
    conf = SparkConf().setAll(silver.spark_settings().items())
    sc = SparkContext.getOrCreate(conf=conf)
    glue_context = GlueContext(sc)
    spark = glue_context.spark_session
    spark.conf.set("spark.sql.session.timeZone", "UTC")

    raw = (spark.read.schema(RAW_SCHEMA).json(src)
           .withColumn("dt", F.regexp_extract(F.input_file_name(), 
            r"departures_(\d{4}-\d{2}-\d{2})", 1))
           .filter(F.col("dt").between(start_date, end_date))
           .cache())

    # Logging if any flights were dropped
    log_dropped_flights(raw)
    
    clean = clean_flights(raw).cache()
    record_count = clean.count()
    if record_count == 0:
        raise RuntimeError(f"No clean flights produced from {src}")


    # Chaning types, and writing new parquet files (overwriting if necessary)
    silver.overwrite_days(date_types(clean))

    if "--START_DATE" in sys.argv:
        print(f"Wrote {record_count} flights for {start_date} -> {end_date} to {dst}")
    else:
        print(f"Wrote {record_count} flights to {dst}")


if __name__ == "__main__":
    main()