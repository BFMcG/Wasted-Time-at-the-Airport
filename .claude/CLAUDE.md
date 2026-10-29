# CLAUDE.md

I am a recent Data Science undergrade who has intermediate python skills and beginner level pyspark skills.

When you write code when prompted, keep it in the session, don't attempt to change or add code to my workspace directly. I'm trying to learn how to code, so when I ask questions, don't write the code for me. Mentor me and teach the correct implementation and why the code is written a certain way. Also, I'm a complete beginner in object oriented programming, but it's something I want to learn. Try to implement it in your code responces but explain it to me fully when you do.

## Commands

```bash
pip install -r requirements.txt          # requests, pytest, boto3, pyspark==3.5.4
pytest                                   # run all tests (pytest.ini sets pythonpath=main, testpaths=test_files)
pytest test_files/test_handler.py        # one file
pytest test_files/test_transformations.py::test_yesterday   # one test
```

`test_transformations.py` spins up a local Spark session (`local[1]`), so it needs Java 17 on the machine (CI installs Temurin 17). The other tests mock all network/AWS calls.

Because `pythonpath = main`, modules are imported flat (`import handler`, `from flight_aware_api import ...`), not as `main.handler`. Keep it that way — the Lambda zip also puts these files at the package root.

## Architecture

A daily AWS data pipeline that tracks departure delays at San Diego (KSAN):

1. **Ingest — Lambda** (`main/handler.py` + `main/flight_aware_api.py`). Gets yesterday's departures from the FlightAware AeroAPI and writes them gzipped as JSON Lines to `s3://$RAW_BUCKET/raw/flightaware/airport=KSAN/departures_<YYYY-MM-DD>.jsonl.gz`, adding an `_ingested_at` field to each row. "Yesterday" means the America/Los_Angeles calendar day, converted to a UTC window. The event can override it with `start`/`end`. The date in the S3 key comes from slicing the `start` timestamp. Env vars: `RAW_BUCKET`, `FLIGHT_API_KEY`. The API client is limited by design: at most 5 pages, a 62s sleep between pages to stay under the rate limit, and it raises if a flight's `actual_off` is outside the window or if no flights come back.
2. **Transform — Glue (PySpark)** (`main/transformations.py`). Reads the raw JSONL with the fixed `RAW_SCHEMA`. It gets `dt` from the filename, not from the data. It dedupes on `(dt, fa_flight_id)`, keeping the latest `_ingested_at`. It splits `ident_icao` into `airline_code`/`flight_number`, computes `runway_delay_secs` (actual_off − actual_out) and `departure_delay_secs`, plus HH:MM:SS display strings, and converts timestamps to PST. Output is Parquet in `s3://$CLEAN_BUCKET/clean/flightaware/airport=KSAN/`, partitioned by `year/month/day`, with dynamic partition overwrite. Glue args: `JOB_NAME`, `RAW_BUCKET`, `CLEAN_BUCKET`, and optionally `START_DATE`/`END_DATE` for backfills (the default is yesterday in UTC). `awsglue` is imported only inside `main()`, so the pure transform functions can be unit tested with plain PySpark.
3. **Serve — Athena views** (`main/sql/`). These build on the `flights.silver_flights` table, which is defined outside this repo (it is the Glue catalog table over the clean bucket). `core/` holds the base views (the `airlines` lookup, then `airlines_tracked`, which joins to silver). `web/` holds the views that feed the website. CD runs the files in glob/filename order, `core/*` before `web/*`, so the numeric prefixes set the dependency order. Number new files to match. Each file must be a single `CREATE OR REPLACE VIEW` statement. The web views share one "total delay" rule: if runway delay is over 1800s, total = runway + departure delay; otherwise it is the departure delay alone.

## CI/CD and branching

- Work lands on `development` and is merged to `main` by PR.
- **CI** (`.github/workflows/ci.yml`) runs `pytest` on Python 3.11 for pushes to `development` and for PRs into `development`/`main`.
- **CD** (`.github/workflows/cd.yml`) runs on every push to `main`. It zips `handler.py` + `flight_aware_api.py` with `requests` (only these; any new Lambda module or dependency must be added to the build step) and deploys them to Lambda (Python 3.14). It copies `transformations.py` to the Glue job's existing script S3 location, then runs every SQL file through the Athena workgroup `flight-aggregations`. AWS settings come from repo variables (`AWS_ROLE_ARN`, `AWS_REGION`, `LAMBDA_FUNC_NAME`, `GLUE_JOB_NAME`) using OIDC.
