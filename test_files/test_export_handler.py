import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, UTC
import json

import export_handler

FROZEN_DATE = datetime(2026, 1, 2, 15, 0, tzinfo=UTC)

# Fixtures
@pytest.fixture(autouse=True)
def env(monkeypatch):
    '''
    Sets the environment for all tests.
    '''
    monkeypatch.setenv("WEB_BUCKET", "my-web-bucket")

@pytest.fixture
def mock_views():
    return {
        "avg_delay_al_yesterday": [
            {"airline_name": "Southwest", "num_flights": 2, "avg_delay_min": 30}
        ],
        "pct_delays_yesterday": [
            {"airline_name": "Southwest", "num_flights": 2, "pct_delay": 50.0}
        ]
    }

@pytest.fixture
def freeze_time():
    '''
    Freezes time to 2026/01/02.
    '''
    with patch("export_handler.datetime") as fake_datetime:
        fake_datetime.now.side_effect = lambda tz=None: FROZEN_DATE.astimezone(tz) if tz else FROZEN_DATE
        yield fake_datetime

@pytest.fixture
def mock_exporter():
    '''
    Replaces AthenaExporter.
    '''
    with patch("export_handler.AthenaExporter") as fake_class:
        yield fake_class

@pytest.fixture
def mock_s3():
    '''
    Replaces boto3.client, s3 and Athena get a fake.
    '''
    fake_s3, fake_athena = MagicMock(), MagicMock()
    clients = {"s3": fake_s3, "athena": fake_athena}
    with patch("export_handler.boto3.client", side_effect=lambda service: clients[service]):
        yield fake_s3

@pytest.fixture
def mock_render_all(mock_rendered_pages):
    '''
    Replacing render_all.
    '''
    with patch("export_handler.pages.SITE.render_all") as fake_render:
        fake_render.return_value = mock_rendered_pages
        yield fake_render

@pytest.fixture
def mock_rendered_pages():
    '''
    Replacing rendered web pages.
    '''
    page_key_1 = "1.html"
    page_key_2 = "2.html"
    html_1 = '<h1>html 1 Title</h1>'
    html_2 = '<h1>html 2 Title</h1>'

    return {page_key_1: html_1,
            page_key_2: html_2}


# Tests
def test_missing_environment(monkeypatch):
    '''
    Tests RuntimeError will be raised if 
    there is no bucket environment.
    '''
    monkeypatch.delenv("WEB_BUCKET")
    with pytest.raises(RuntimeError) as error:
        export_handler.handler({}, None)

    assert str(error.value) == "WEB_BUCKET environment variable is not set"


@pytest.mark.usefixtures("freeze_time")
def test_view_failure(mock_s3, mock_exporter):
    '''
    Test if a view fails nothing gets written to s3 bucket
    '''
    mock_exporter.return_value.fetch_views.side_effect = RuntimeError("Query FAILED")

    with pytest.raises(RuntimeError, match="Query FAILED"):
        export_handler.handler({}, None)

    assert mock_s3.put_object.call_count == 0


@pytest.mark.usefixtures("freeze_time")
def test_writes_json_s3(mock_s3, mock_exporter, mock_views):
    '''
    Tests that the bucket has the correct objects
    and the return statement is correct.
    '''

    mock_exporter.return_value.fetch_views.return_value = mock_views

    result = export_handler.handler({}, None)

    # Checking exporter was built properly
    settings = mock_exporter.call_args.kwargs

    assert settings["workgroup"] == "flight-aggregations"
    assert settings["database"] == "flights"

    # Checking document (exctracting for Body in s3)
    args = mock_s3.put_object.call_args_list[0].kwargs
    document = json.loads(args["Body"])
    assert document['data_date'] == "2026-01-01"
    assert document["views"] == mock_views
    assert document["generated_at"] == FROZEN_DATE.isoformat()

    # Checking s3 bucket
    assert args["Bucket"] == "my-web-bucket"
    assert args["Key"] == "data/web/airport=KSAN/2026-01-01.json"
    assert args["ContentType"] == "application/json"

    # Checking return value
    assert result == {
        "statusCode": 200,
        "bucket": "my-web-bucket",
        "key": args["Key"],
        "record_count": 2,
        "date": "2026-01-01"
    }

@pytest.mark.usefixtures("freeze_time")
def test_write_webpage_s3(mock_s3, mock_exporter, mock_views, 
                          mock_render_all, mock_rendered_pages):
    '''
    Tests that the bucket has the correct objects
    and the return statement is correct.
    '''
    mock_exporter.return_value.fetch_views.return_value = mock_views

    export_handler.handler({}, None)

    # Same views JSON received
    document = mock_render_all.call_args.args[0]
    assert document["data_date"] == "2026-01-01"
    assert document["views"] == mock_views

    # Making call
    calls = mock_s3.put_object.call_args_list
    assert len(calls) == 1 + len(mock_rendered_pages)

    # Itterating through pages and skipping JSON file
    page_calls = [c.kwargs for c in calls[1:]]
    for args, (page_key, html) in zip(page_calls, mock_rendered_pages.items()):
        assert args["Bucket"] == "my-web-bucket"
        assert args["Key"] == page_key
        assert args["Body"] == html
        assert args["ContentType"] == "text/html; charset=utf-8"
        assert args["CacheControl"] == "max-age=300"