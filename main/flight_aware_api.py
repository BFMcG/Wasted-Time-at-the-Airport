import os
import time
from urllib.parse import parse_qs, urlparse

import requests

# To do class object oriented creting api urls
my_api_key = os.environ.get("FLIGHT_API_KEY")
query_url = "https://aeroapi.flightaware.com/aeroapi/airports/KSAN/flights/departures"

class OutsideDateRange(ValueError):
    pass

class RateLimitExceeded(RuntimeError):
    pass

def get_flight_data(api_key: int, lookup_date_min: str, lookup_date_max: str):
    '''
    Given yesterday's date range in UTC, and the API key, returns the neccissary
    data from the API.
    '''

    header = {
        "x-apikey": api_key
    }

    flight_params = {
        "start": lookup_date_min,
        "end": lookup_date_max,
        "type": "Airline",
        "max_pages": 10,
        "cursor": None
    }

    flights = []
    request_count = 1

    while True:
        if request_count > 5:
            print("returning 5 pages of flights")
            break
        r = requests.get(query_url, headers=header, params=flight_params)
        print(f"Request number {request_count}")

        if r.status_code == 429:
            raise RateLimitExceeded(
                f"Code 429: Rate limit exceeded on request {request_count}"
            )
        r.raise_for_status()
        data = r.json()
        flights.extend(data.get("departures", []))

        links = data.get("links")
        if not links:
            print("No link")
            break

        next_page = links.get("next")
        if not next_page:
            print("No next page")
            break

        cursor = parse_qs(urlparse(next_page).query).get("cursor", [None])[0]
        if not cursor:
            print("No cursor")
            break
        flight_params["cursor"] = cursor

        print("Waiting for 62 seconds...")
        time.sleep(62) # Sleep for 62 seconds to avoid rate limit
        print("Continuing to next page...")

        request_count += 1

    #Checking if all flights are within date range
    no_actual_off = 0

    for idx, flight in enumerate(flights):
        actual_off = flight.get("actual_off")
        if not actual_off:
            no_actual_off += 1
            continue
        if actual_off < lookup_date_min or actual_off > lookup_date_max:
            raise ValueError(f"Error: Flight {idx} is outside of scheduled date range: {actual_off}")
    print("No scheduled out: ", no_actual_off)

    # Checking if any flights were returned
    if len(flights) == 0:
        raise ValueError(f"No flights were recorded from the API")


    return flights

