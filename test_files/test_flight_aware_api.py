from unittest.mock import MagicMock, patch

import pytest
from flight_aware_api import get_flight_data


# flight_aware_api test fixtures and mock_response
@pytest.fixture
def mock_get():
    '''
    Replaces requests.get.
    '''
    with patch("flight_aware_api.requests.get") as fake:
        yield fake


@pytest.fixture
def mock_sleep():
    '''
    Replaces time.sleep so tests don't wait 62 seconds.
    '''
    with patch("flight_aware_api.time.sleep") as fake:
        yield fake


@pytest.fixture
def mock_flights_page():
    return [
        {"flight_number": "1234", "ident_iata": "SWA"},
        {"flight_number": "5678", "ident_iata": "DAL"},
        {"flight_number": "9012", "ident_iata": "AAL"}
    ]

@pytest.fixture
def mock_flights_range():
    return [
        {"flight_number": "1234", "ident_iata": "SWA",
         "scheduled_out": "2026-01-01T12:00:00Z"},   # in range
        {"flight_number": "9012", "ident_iata": "AAL",
         "scheduled_out": "2026-01-03T12:00:00Z"},   # out of range
    ]
 
 
@pytest.fixture
def mock_window():
    return {"start": "2026-01-01T07:00:00Z", "end": "2026-01-02T07:00:00Z"}
 
 
def mock_response(flights, next_link=None, num_pages=1):
    '''
    mocks the response from requests.get() for testing get_flights.
    Adds next link to mock flights if next_link is provided.
    '''
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "departures": flights,
        "links": {"next": next_link} if next_link else None,
        "num_pages": num_pages,
    }
    return response
 

# API tests
def test_single_page_returns_flights(mock_get, mock_flights_page, mock_window):
    '''
    Only one page worth of flights with no link,
    only makes one request
    '''
    mock_get.return_value = mock_response(mock_flights_page) # No link, single page
 
    flights = get_flight_data(None, mock_window["start"], mock_window["end"])
 
    assert flights == mock_flights_page
    assert mock_get.call_count == 1
 

def test_stops_after_five_requests(mock_get, mock_sleep, mock_flights_page, mock_window):
    '''
    The last page of every request has a next link, 
    so more data is always available.
    '''
    # 10 pages worth of flights
    flights_per_request = mock_flights_page * 10 
    mock_get.side_effect = [
        mock_response(
            flights_per_request,
            next_link=f"/flights?cursor=request{i + 1}",
            num_pages=10,
        )
        for i in range(6)  # a 6th response exists, but must never be requested
    ]
 
    result = get_flight_data(None, mock_window["start"], mock_window["end"])
 
    # 5 requests x 10 pages = 50 pages, and the 5th request's next link is ignored.
    assert mock_get.call_count == 5
    assert len(result) == 5 * len(flights_per_request)

    # Using mock_sleep
    assert mock_sleep.call_count == 5

def test_cursor_points_to_next_page(mock_get, mock_sleep, mock_flights_page, mock_window):
    '''
    Page that has a link with a cursor will point to the next page,
    and the next page has the link
    '''
    # page without next_link
    page_two = mock_flights_page
    mock_get.side_effect = [
        mock_response(mock_flights_page, next_link="/flights?cursor=abc123"),
        mock_response(page_two),
    ]
 
    flights = get_flight_data(None, mock_window["start"], mock_window["end"])
 
    assert mock_get.call_count == 2
    # The second request must carry the cursor from the first page's links.next
    second_call = mock_get.call_args_list[1]
    assert "abc123" in str(second_call)
    assert flights == mock_flights_page + page_two

    # Using mock_sleep
    assert mock_sleep.call_count == 1

def test_outside_date_range(mock_get, mock_flights_range, mock_window):
    '''
    One flight is scheduled after the window ends, so get_flight_data
    should raise a ValueError naming that flight's index.
    Flights missing scheduled_out are skipped, not treated as errors.
    '''
    mock_get.return_value = mock_response(mock_flights_range)

    with pytest.raises(ValueError, match="Flight 1 is outside of scheduled date range"):
        get_flight_data(None, mock_window["start"], mock_window["end"])