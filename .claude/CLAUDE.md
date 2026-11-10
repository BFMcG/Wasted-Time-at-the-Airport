# CLAUDE.md

I am a recent Data Science undergrade who has intermediate python skills and beginner level pyspark skills.

When you write code when prompted, keep it in the session, don't attempt to change or add code to my workspace directly. Mentor me and teach the correct implementation and why the code is written a certain way. Also, I'm a complete beginner in object oriented programming, but it's something I want to learn. Try to implement it in your code responces but explain it to me fully when you do.

## Commands

```bash
pip install -r requirements.txt          # requests, pytest, boto3, pyspark==3.5.4
pytest                                   # run all tests (pytest.ini sets pythonpath=main, testpaths=test_files)
pytest test_files/test_api_handler.py        # one file
pytest test_files/test_transformations.py::test_yesterday   # one test
```

`test_transformations.py` and `test_sql.py` use the session-scoped `spark` fixture in `test_files/conftest.py` (`local[1]`, session timezone UTC), so they need Java 17 on the machine (CI installs Temurin 17). The other tests mock all network/AWS calls.

`test_sql.py` runs the real view SQL files on Spark. It rewrites `CREATE OR REPLACE VIEW` to `TEMP VIEW`, removes the `flights.` prefix, and swaps `date(current_timestamp AT TIME ZONE 'America/Los_Angeles')` for a fixed `DATE '2026-01-03'`. New views must use that exact "today" expression and Spark-compatible SQL, or the tests won't be able to run them.

Because `pythonpath = main`, modules are imported flat (`import api_handler`, `from athena_exporter import AthenaExporter`), not as `main.api_handler`. Keep it that way — the Lambda zips also put these files at the package root.

## Architecture

A daily AWS data pipeline that tracks departure delays at San Diego (KSAN):

1. **Ingest — Lambda** (`main/api_handler.py` + `main/flight_aware_api.py`). Gets yesterday's departures from the FlightAware AeroAPI and writes them gzipped as JSON Lines to `s3://$RAW_BUCKET/raw/flightaware/airport=KSAN/departures_<YYYY-MM-DD>.jsonl.gz`, adding an `_ingested_at` field to each row. "Yesterday" means the America/Los_Angeles calendar day, converted to a UTC window. The event can override it with `start`/`end`. The date in the S3 key comes from slicing the `start` timestamp. Env vars: `RAW_BUCKET`, `FLIGHT_API_KEY`. The API client is limited by design: at most 5 pages, a 62s sleep between pages to stay under the rate limit, and it raises if a flight's `actual_off` is outside the window or if no flights come back.
2. **Transform — Glue (PySpark)** (`main/transformations.py`). Reads the raw JSONL with the fixed `RAW_SCHEMA`. It gets `dt` from the filename, not from the data. `clean_flights` chains small pure functions: `parse_timestamps` → `dedupe_flights` (on `(dt, fa_flight_id)`, keeping the latest `_ingested_at`, dropping null ids) → `drop_missing_departure` (drops rows with null `departure_delay`) → `split_ident` (`ident_icao` → `airline_code`/`flight_number`) → `add_runway_delay` (`runway_delay` = actual_off − actual_out in seconds, negative → null) → `pst_time`. Output columns: `dt, fa_flight_id, airline_code, flight_number, code_icao, scheduled_out, actual_out, actual_off, departure_delay, runway_delay` (delays are int seconds). `log_dropped_flights` prints how many rows dedupe and the null-departure filter dropped; it is a separate function so the counts can be tested. Output is Parquet in `s3://$CLEAN_BUCKET/clean/flightaware/airport=KSAN/`, partitioned by `year/month/day` (from `add_date_parts`), with dynamic partition overwrite. The job raises if no clean rows are produced. Glue args: `JOB_NAME`, `RAW_BUCKET`, `CLEAN_BUCKET`, and optionally `START_DATE`/`END_DATE` for backfills (the default is yesterday in UTC). `awsglue` is imported only inside `main()`, so the pure transform functions can be unit tested with plain PySpark.
3. **Serve — Athena views** (`main/sql/`). These build on `flights.silver_flights`. Its DDL is in `main/sql/ddl/silver_flights.sql`: an external Parquet table over the clean bucket, partitioned by `airport/year/month/day` with partition projection, so no crawler or `MSCK REPAIR` is needed. CD does **not** run the DDL; apply it by hand if it changes. `core/` holds the base views (`00_airlines` lookup, then `01_airlines_tracked`, which joins silver to airlines and adds `total_delay_secs`). `web/` (`10_`–`17_`) holds the `web_*` views that feed the website (top delays, avg delay per airline, % delayed, total delay, each with a `_today` and a `_month` version). CD runs the files in glob/filename order, `core/*` before `web/*`, so the numeric prefixes set the dependency order. Number new files to match. Each file must be a single `CREATE OR REPLACE VIEW` statement. The "total delay" rule is defined once in `airlines_tracked`: if `runway_delay` > 1800s, total = `departure_delay + (runway_delay − 1800)`; otherwise it is `departure_delay` alone. Web views filter on the `year/month/day` partition columns (not `dt`) so Athena prunes partitions, and "today" means yesterday's LA date, since data lands the next morning. Running them between midnight and when the pipeline finishes returns empty results.
4. **Export — Lambda** (`main/export_handler.py` + `main/athena_exporter.py`). `AthenaExporter` is a class that wraps a boto3 Athena client (workgroup `flight-aggregations`, database `flights`). It starts every query first, then polls each one with a timeout (`wait_for_query`), then pages through the results (`get_rows`), converting Athena types to Python types. Only `varchar`/`integer`/`bigint`/`double`/`boolean` are supported; any other type raises `ValueError`, so new view columns must use one of those. `fetch_views` returns `{view name without "web_": rows}`. The handler runs every view in `VIEWS` and writes one JSON document `{data_date, views, generated_at}` to `s3://$WEB_BUCKET/data/web/airport=KSAN/<YYYY-MM-DD>.json`, where the date is yesterday in LA. Env var: `WEB_BUCKET`. A new web view must also be added to `VIEWS`. It uses only boto3, which the Lambda runtime provides.

## CI/CD and branching

- Work lands on `development` and is merged to `main` by PR.
- **CI** (`.github/workflows/ci.yml`) runs `pytest` on Python 3.11 for pushes to `development` and for PRs into `development`/`main`.
- **CD** (`.github/workflows/cd.yml`) runs on every push to `main` (or manually through `workflow_dispatch`), on Python 3.14. It builds two zips, and each one includes only the files named in its build step, so any new module or dependency must be added there:
  - `api_function.zip`: `api_handler.py` + `flight_aware_api.py` + `requests` → ingestion Lambda (`LAMBDA_INGES_NAME`).
  - `export_function.zip`: `export_handler.py` + `athena_exporter.py` → export Lambda (`LAMBDA_EXP_NAME`).
  
  In order, it deploys the ingestion Lambda, copies `transformations.py` to the Glue job's existing script S3 location, runs `core/*.sql` then `web/*.sql` through the Athena workgroup `flight-aggregations` (it stops on the first failed query), and finally deploys the export Lambda. AWS settings come from repo variables (`AWS_ROLE_ARN`, `AWS_REGION`, `LAMBDA_INGES_NAME`, `LAMBDA_EXP_NAME`, `GLUE_JOB_NAME`) using OIDC.
