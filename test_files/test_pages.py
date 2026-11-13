import pytest
from pages import missing_check, DelayCounter, HomePage



@pytest.fixture
def mock_miss_doc():
    return {
        "data_date": "2026-01-01",
        "views": {"flights": [{"FLT1": "1234", "FLT2": "5678"}]},
        "generated_at": "2026-01-01"
    }

def test_missing_check(mock_miss_doc):
    normal_result = missing_check(mock_miss_doc["views"], "flights")
    no_view = missing_check(mock_miss_doc["views"], "test_name")
    empty_flights = missing_check({"flights": []}, "flights")
    
    assert normal_result == {"FLT1": "1234", "FLT2": "5678"}
    assert no_view == {}
    assert empty_flights == {}


# DelayCounter
def test_total_seconds():
    delay_all = DelayCounter(1, 1, 1, 1)
    delay_no_hrs = DelayCounter(1, 0, 1, 1)

    ts_all = delay_all.total_seconds
    ts_no_hrs = delay_no_hrs.total_seconds

    assert ts_all == 90061
    assert ts_no_hrs == 86461

def test_to_html():
    delay_all = DelayCounter(100, 2, 3, 0)

    result = delay_all.to_html()

    expected = [(100, "days"), (2, "hours"), (3, "min"), (0, "sec")]

    for num, label in expected:
        assert (f'<div class="unit"><span class="value">{num:02d}</span>'
                f'<span class="label">{label}</span></div>'
            ) in result

    assert result.count('<span class="colon">:</span>') == 3


# HomePage
@pytest.fixture
def mock_home_document():
    return {
            "data_date": "2026-01-01",
            "views": {"total_delay_yesterday": 
                    [{"delayed_flights_day": 10,
                      "days_wasted": 1, 
                      "hours_wasted": 1,
                      "minutes_wasted": 1,
                      "secs_wasted": 1}],
                    "total_delay_month":
                    [{"delayed_flights_month": 100,
                      "days_wasted": 100, 
                      "hours_wasted": 10,
                      "minutes_wasted": 1,
                      "secs_wasted": 0}]},
            "generated_at": "2026-01-01"
    }

def test_home_body(mock_home_document):
    result = HomePage().body(mock_home_document)

    # Title
    assert "<h1>Time Wasted at the Airport</h1>" in result

    #_counter_block
    # Total Seconds
    assert result.count('<section class="counter-block">') == 2
    assert 'data-total="90061"' in result
    assert 'data-total="8676060"' in result

    # Values
    assert result.count('<span class="colon">:</span>') == 6
    assert result.count('class="value">01<') == 5
    assert 'class="value">100<' in result
    assert 'class="value">10<' in result
    assert 'class="value">00<' in result

    # Labels
    assert result.count('<span class="label">days</span></div>') == 2
    assert result.count('<span class="label">hours</span></div>') == 2
    assert result.count('<span class="label">min</span></div>') == 2
    assert result.count('<span class="label">sec</span></div>') == 2


def test_home_body_missing():
    result = HomePage().body({"views": {}})

    # Title
    assert "<h1>Time Wasted at the Airport</h1>" in result

    # Total Seconds
    assert result.count('data-total="0"') == 2

    # Values
    assert result.count('<span class="colon">:</span>') == 6
    assert result.count('class="value">00<') == 8

    # Labels
    assert result.count('<span class="label">days</span></div>') == 2
    assert result.count('<span class="label">hours</span></div>') == 2
    assert result.count('<span class="label">min</span></div>') == 2
    assert result.count('<span class="label">sec</span></div>') == 2