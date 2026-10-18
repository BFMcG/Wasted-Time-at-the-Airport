import os
import gzip
import json
from datetime import datetime
from unittest.mock import patch
 
import pytest
 
os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")
 
from flight_aware_api import get_flight_data
import handler


# handler test fixtures
@pytest.fixture
def mock_flights():
    return [
        {"fa_flight_id": "FLT1", "ident": "SWA100", "origin": "SAN", "destination": "KLAX"},
        {"fa_flight_id": "FLT2", "ident": "UAL200", "origin": "SAN", "destination": "KSFO"},
    ]

@pytest.fixture
def mock_window():
    return {"start": "2026-01-01T07:00:00Z", "end": "2026-01-02T07:00:00Z"}

@pytest.fixture
def mock_s3():
    '''
    Replaces the S3 bucket.
    '''
    with patch("handler.s3") as fake:
        yield fake
 
@pytest.fixture
def mock_get_flight_data():
    '''
    Replaces get_flight_data function for testing the handler.
    '''
    with patch("handler.get_flight_data") as fake:
        yield fake

@pytest.fixture(autouse=True)
def env(monkeypatch):
    '''
    Sets the environment for all tests.
    '''
    monkeypatch.setenv("RAW_BUCKET", "my-raw-bucket")
    monkeypatch.setenv("FLIGHT_API_KEY", "test-key")



# Handler tests
def test_yesterday_date():
    '''
    Testing if yesterday's date string is in the right format
    and the range is exactly one day long.
    '''
    start, end = handler.yesterday_date()

    assert start.endswith("T07:00:00Z")
    assert end.endswith("T07:00:00Z")

    parse_start = datetime.fromisoformat(start).date()
    parse_end = datetime.fromisoformat(end).date()

    assert (parse_end - parse_start).days == 1
 
 
def test_build_key():
    '''
    Testing the S3 key build is proper
    '''
    key = handler.build_key("2026-01-01T07:00:00Z")
    assert key == "raw/flightaware/airport=SAN/departures_2026-01-01"
 
 
def test_writes_flights_to_s3(mock_s3, mock_get_flight_data, mock_flights, mock_window):
    '''
    Tests S3 environment, the flights are in teh json body,
    and all of the expected return values match.
    '''
    mock_get_flight_data.return_value = mock_flights

    result = handler.handler(mock_window, None)
 
    # Checking mock_s3 bucket
    args = mock_s3.put_object.call_args.kwargs
    assert args["Bucket"] == "my-raw-bucket"
    assert args["Key"] == "raw/flightaware/airport=SAN/departures_2026-01-01"
 
    # Unzipping mock_s3 to count flights
    text = gzip.decompress(args["Body"]).decode("utf-8")
    lines = text.split("\n")
    assert len(lines) == 2
    # Checking first flight and _ingested_at
    first_flight = json.loads(lines[0])
    assert first_flight["fa_flight_id"] == "FLT1"
    assert "_ingested_at" in first_flight
 
    # Checking return value of S3 bucket
    assert result["statusCode"] == 200
    assert result["bucket"] == "my-raw-bucket"
    assert result["key"] == args["Key"]
    assert result["record_count"] == 2
    assert result["window"] == mock_window
 
 
def test_no_flights(mock_s3, mock_get_flight_data, mock_window):
    '''
    Testing if flights is empty ([]) an error is raised
    and no nothing is uploaded to flights.
    '''
    mock_get_flight_data.return_value = []

    with pytest.raises(RuntimeError) as error:
        handler.handler(mock_window, None)

    expected = (
        f"statusCode: 200, flights empty for {mock_window['start']} -> {mock_window['end']}."
    )
    assert str(error.value) == expected

    # Nothing should be uploaded when there are no flights
    mock_s3.put_object.assert_not_called()
 
 
def test_missing_env(monkeypatch, mock_get_flight_data):
    '''
    Testing if there is no bucket, 
    if bucket but no API key,
    API is never called if poor environment set up.
    '''
    # No bucket
    monkeypatch.delenv("RAW_BUCKET")
    with pytest.raises(RuntimeError) as error:
        handler.handler({}, None)

    expected = ("RAW_BUCKET environment variable is not set")

    assert str(error.value) == expected
 
    # Bucket, but no API key
    monkeypatch.setenv("RAW_BUCKET", "my-raw-bucket")
    monkeypatch.delenv("FLIGHT_API_KEY")
    with pytest.raises(RuntimeError) as error2:
        handler.handler({}, None)

    expected2 = ("FLIGHT_API_KEY environment variable is not set")

    assert str(error2.value) == expected2
 
    # The API should never be called if setup is wrong
    mock_get_flight_data.assert_not_called()