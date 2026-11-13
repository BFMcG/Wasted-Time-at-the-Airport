from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, UTC
import boto3
import os
import json

from athena_exporter import AthenaExporter
import pages

S3_PREFIX = "data/web"
AIRPORT = "KSAN"

VIEWS = [
    "web_avg_delay_al_month",
    "web_avg_delay_al_yesterday",
    "web_pct_delays_month",
    "web_pct_delays_yesterday",
    "web_top_delays_month",
    "web_top_delays_yesterday",
    "web_total_delay_month",
    "web_total_delay_yesterday"
]


def handler(event, context):
    '''
    Lambda handler that saves Athena queries in gold bucket 
    as JSON files.
    '''

    zone = ZoneInfo("America/Los_Angeles")
    data_date = (datetime.now(zone).date() - timedelta(days=1)).isoformat()
    bucket = os.environ.get("WEB_BUCKET")

    if not bucket:
        raise RuntimeError("WEB_BUCKET environment variable is not set")

    s3 = boto3.client("s3")

    if context:
        print(
            f"Request {context.aws_request_id}: fetching {data_date}, "
            f"{context.get_remaining_time_in_millis() / 1000:.0f}s remaining"
        )
    else:
        print("No context available for request")

    athena_exp = AthenaExporter(
        athena_client=boto3.client("athena"),
        workgroup="flight-aggregations",
        database="flights"
    )


    all_views = athena_exp.fetch_views(VIEWS)

    document = {
        "data_date": data_date,
        "views": all_views,
        "generated_at": datetime.now(UTC).isoformat()
    }


    # JSON file
    key = f"{S3_PREFIX}/airport={AIRPORT}/{data_date}.json"

    s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(document),
            ContentType="application/json"
        )

    print(f"Wrote {len(VIEWS)} views to s3://{bucket}/{key}")


    # Webpage files
    rendered_pages = pages.SITE.render_all(document)

    for page_key, html in rendered_pages.items():
        s3.put_object(
            Bucket=bucket,
            Key=page_key,
            Body=html,
            ContentType="text/html; charset=utf-8",
            CacheControl="max-age=300"
        )
        print(f"Wrote page to s3://{bucket}/{page_key}")
    
    return {
        "statusCode": 200,
        "bucket": bucket,
        "key": key,
        "record_count": sum(len(rows) for rows in all_views.values()),
        "date": data_date
    }