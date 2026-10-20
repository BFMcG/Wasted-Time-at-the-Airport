import os
import json
import gzip
from datetime import datetime, timedelta, timezone
 
import boto3
 
from flight_aware_api import get_flight_data
 
s3 = boto3.client("s3")
 
Airport = "SAN"
S3_prefix = "raw/flightaware"
 
 
def yesterday_date() -> tuple[str, str]:
    '''
    Yesterday's full UTC day.
    '''
    max_date = datetime.now(timezone.utc).replace(hour=7, minute=0, second=0, microsecond=0)
    min_date = max_date - timedelta(days=1)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return min_date.strftime(fmt), max_date.strftime(fmt)


def build_key(date_window) -> str:
    '''
    Building a the key for the S3 bucket for the daily flight data.
    window_start: "YYYY-MM-DD" format for yesterday's flight data.
    '''
    dt = date_window[:-10]
    return (
        f"{S3_prefix}/airport={Airport}/"
        f"departures_{dt}"
    )
 
 
def handler(event, context):
    event = event or {}
 
    bucket = os.environ.get("RAW_BUCKET")
    api_key = os.environ.get("FLIGHT_API_KEY")
    if not bucket:
        raise RuntimeError("RAW_BUCKET environment variable is not set")
    if not api_key:
        raise RuntimeError("FLIGHT_API_KEY environment variable is not set")
 
    min_start, max_end = yesterday_date()
    start = event.get("start", min_start)
    end = event.get("end", max_end)

    if context:
        print(
            f"Request {context.aws_request_id}: fetching {start} -> {end}, "
            f"{context.get_remaining_time_in_millis() / 1000:.0f}s remaining"
        )
    else:
        print(f"No context available for request")
 
    flights = get_flight_data(api_key, start, end)
 
    if not flights:
        raise RuntimeError(f"statusCode: 200, flights empty for {start} -> {end}.")
 
    now = datetime.now(timezone.utc)
    ingested_at = now.isoformat()
 
    # JSON Lines: one flight per line, with an ingestion timestamp
    body = "\n".join(
        json.dumps({**flight, "_ingested_at": ingested_at}) for flight in flights
    )
 
    key = build_key(start)
 
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=gzip.compress(body.encode("utf-8")),
        ContentType="application/x-ndjson",
        ContentEncoding="gzip",
    )
 
    print(f"Wrote {len(flights)} flights to s3://{bucket}/{key}")
 
    return {
        "statusCode": 200,
        "bucket": bucket,
        "key": key,
        "record_count": len(flights),
        "window": {"start": start, "end": end},
    }