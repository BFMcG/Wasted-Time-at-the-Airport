from athena_exporter import AthenaExporter
import pytest
from unittest.mock import MagicMock


QUERY_ID = "1234"

# Fixtures and additional functions
@pytest.fixture
def mock_exporter():

    return AthenaExporter(
    athena_client = MagicMock(),
    workgroup = "test-workgroup",
    database = "test-db",
    poll_seconds = 0,
    poll_timeout = 5,
    )

@pytest.fixture
def type_converter():
    return [
        ("United", "varchar", "United"),
        ("2",      "bigint",  2),
        ("33.33",  "double",  33.33),
        ("true",   "boolean", True),
        (None,     "bigint",  None),
    ]

@pytest.fixture
def mock_fetch():

    response = MagicMock()
    response.start_query.side_effect = [QUERY_ID, QUERY_ID + "5"]
    response.get_rows.side_effect = [
        [{'airline_name': 'United', 'num_flights': 2}],
        [{'airline_name': 'Delta', 'num_flights': None}]
        ]

    return response


def mock_rows(number_of_pages=1):
    column_info = [{"Name": "airline_name", "Type": "varchar"},
                   {"Name": "num_flights",  "Type": "bigint"}]

    page_1 = {
    "ResultSet": {
        "Rows": [
        {"Data": [{"VarCharValue": "airline_name"}, {"VarCharValue": "num_flights"}]},
        {"Data": [{"VarCharValue": "United"},       {"VarCharValue": "2"}]},            
        {"Data": [{"VarCharValue": "Delta"},        {}]}                               
            ],
        "ResultSetMetadata": {"ColumnInfo": column_info}
        }
    }

    page_2 = {
    "ResultSet": {
        "Rows": [
        {"Data": [{"VarCharValue": "American"},     {"VarCharValue": "2"}]},            
        {"Data": [{"VarCharValue": "SouthWest"},    {"VarCharValue": "3"}]},
        {"Data": [{"VarCharValue": "JetBlue"},      {"VarCharValue": "1"}]}                           
            ],
        "ResultSetMetadata": {"ColumnInfo": column_info}
        }
    }

    if number_of_pages == 1:
        return [page_1]
    elif number_of_pages == 2:
        return [page_1, page_2]
    else:
        raise ValueError("Only 1 or 2 mock pages available")


def state(status):
    '''
    State of query running.
    '''
    return {'QueryExecution': {'Status': {'State': status}},
            'QueryExecutionId': QUERY_ID}


# Tests
def test_start_query(mock_exporter):
    '''
    Testing that the query id is collected from a mock response
    '''
    athena = mock_exporter.athena_client

    # Test query ids
    athena.start_query_execution.return_value = {'QueryExecutionId': QUERY_ID,
                                                'SomethingElse': '5678'}

    assert mock_exporter.start_query("SELECT * FROM test_table") == QUERY_ID


def test_wait_for_query(mock_exporter):
    '''
    Testing runtime errors work properly.
    '''
    athena = mock_exporter.athena_client

    # SUCCEEDED
    athena.get_query_execution.return_value = state('SUCCEEDED')
    assert mock_exporter.wait_for_query(QUERY_ID) is None

    # FAILED
    athena.get_query_execution.return_value = state('FAILED')
    with pytest.raises(RuntimeError):
        mock_exporter.wait_for_query(QUERY_ID)

    # CANCELLED
    athena.get_query_execution.return_value = state('CANCELLED')
    with pytest.raises(RuntimeError):
        mock_exporter.wait_for_query(QUERY_ID)
        
    # TIMEOUT
    mock_exporter.poll_timeout = 0
    athena.get_query_execution.return_value = state('RUNNING')
    with pytest.raises(TimeoutError):
        mock_exporter.wait_for_query(QUERY_ID)

            
def test_get_rows(mock_exporter):
    '''
    Testing rows are collected and formated properly
    '''
    athena = mock_exporter.athena_client

    # One page
    (athena.get_paginator.return_value
            .paginate.return_value) = mock_rows()
    
    assert mock_exporter.get_rows(QUERY_ID) == [
        {'airline_name': 'United', 'num_flights': 2},
        {'airline_name': 'Delta', 'num_flights': None}
        ]

    # Two pages
    (athena.get_paginator.return_value
            .paginate.return_value) = mock_rows(number_of_pages=2)

    assert mock_exporter.get_rows(QUERY_ID) == [
        {'airline_name': 'United',    'num_flights': 2},
        {'airline_name': 'Delta',     'num_flights': None},
        {'airline_name': 'American',  'num_flights': 2},
        {'airline_name': 'SouthWest', 'num_flights': 3},
        {'airline_name': 'JetBlue',   'num_flights': 1}
        ]


def test_convert(mock_exporter, type_converter):
    '''
    Testing types are converted properly
    '''

    for value, a_type, output in type_converter:
        result = mock_exporter._convert(value, a_type)
        assert result == output, f"_convert({value}, {a_type}) gave {result}"
        assert type(result) is type(output), f"Unequal types for {a_type}"


def test_fetch_views(mock_exporter, mock_fetch):
    '''
    Testing the fetch views come out as expected
    '''
    views = ["web_avg_delay_al_month",
            "web_avg_delay_al_yesterday"]

    mock_exporter.start_query = mock_fetch.start_query
    mock_exporter.wait_for_query = mock_fetch.wait_for_query
    mock_exporter.get_rows = mock_fetch.get_rows

    assert mock_exporter.fetch_views(views) == {
        "avg_delay_al_month": [{'airline_name': 'United', 'num_flights': 2}],
        "avg_delay_al_yesterday": [{'airline_name': 'Delta', 'num_flights': None}]
        }
            