"""flights.py - find our flight in the OpenSky data and estimate the landing time.

Owner: Christian
Status: prototype for D4, two TODOs still open (see below).
"""

import math
from datetime import timedelta

# airline code (flight number) -> callsign prefix (radio)
AIRLINES = {
    "LH": "DLH",  # Lufthansa
    "UA": "UAL",  # United
    "AA": "AAL",  # American
    "EW": "EWG",  # Eurowings
    "DE": "CFG",  # Condor
}

# positions of the fields in one OpenSky state vector
CALLSIGN = 1
LAST_CONTACT = 4
LON = 5
LAT = 6
ALTITUDE = 7
ON_GROUND = 8
VELOCITY = 9

MIN_SPEED_MS = 50  # slower than this: no useful estimate


def to_callsign(flight_number, airlines):
    """Turn a flight number like "LH 123" into a callsign like "DLH123"."""
    text = flight_number.replace(" ", "").upper()
    code = text[:2]
    number = text[2:]
    # TODO: callsigns like "DLH4AB" should stay as they are
    if code not in airlines or not number.isdigit():
        return None
    return airlines[code] + number


def parse_state(vector):
    """Turn one state vector (list) into a dictionary with field names.
    Returns None if a field we need is missing or null."""
    try:
        needed = [vector[CALLSIGN], vector[LON], vector[LAT], vector[ON_GROUND]]
    except (IndexError, TypeError):
        return None
    if None in needed:
        return None
    return {
        "callsign": vector[CALLSIGN].strip(),
        "last_contact": vector[LAST_CONTACT],
        "lon": vector[LON],
        "lat": vector[LAT],
        "altitude": vector[ALTITUDE],
        "on_ground": vector[ON_GROUND],
        "velocity": vector[VELOCITY],
    }


def find_flight(states, callsign):
    """Find our flight in the list of aircraft (dictionaries from parse_state).
    Returns the dictionary or None."""
    for aircraft in states:
        if aircraft["callsign"] == callsign:
            # TODO: skip positions older than 60 seconds
            return aircraft
    return None


def haversine_km(lat1, lon1, lat2, lon2):
    """Distance between two points on earth in km (haversine formula)."""
    r = 6371  # earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def estimate_landing(distance_km, speed_ms, now):
    """Estimated landing time without the approach buffer (main.py adds it).
    Returns None if the speed is missing or too low."""
    if speed_ms is None or speed_ms < MIN_SPEED_MS:
        return None
    seconds = distance_km * 1000 / speed_ms
    return now + timedelta(seconds=seconds)


if __name__ == "__main__":
    # quick manual test with made-up data
    from datetime import datetime

    sample = [
        ["3c6444", "DLH123  ", "Germany", 1763479190, 1763479195, 3.95, 51.5, 9800.0, False, 238.0],
        ["a1b2c3", "UAL960  ", "United States", 1763479190, 1763479195, -40.2, 55.1, 11000.0, False, 250.0],
    ]
    callsign = to_callsign("LH 123", AIRLINES)
    states = [s for s in (parse_state(v) for v in sample) if s]
    flight = find_flight(states, callsign)
    print(flight)
    km = haversine_km(flight["lat"], flight["lon"], 50.0333, 8.5706)
    print(round(km), "km to Frankfurt")
    print("landing:", estimate_landing(km, flight["velocity"], datetime.now()).strftime("%H:%M"))
