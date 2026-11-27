"""Airport Planner - main.py (owner: Tyrique)

This is the file we start: python main.py
It asks the user for input, calls the functions from api_client.py and
flights.py, prints the result and saves it to a CSV file.
"""

import csv
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from api_client import build_url, fetch_json, zip_to_coords, drive_minutes
from flights import to_callsign, parse_state, find_flight, haversine_km, estimate_landing

# airline code -> callsign prefix
AIRLINES = {"LH": "DLH", "UA": "UAL", "AA": "AAL", "DL": "DAL",
            "EW": "EWG", "LX": "SWR", "OS": "AUA", "BA": "BAW"}

# our airports with position and time zone
AIRPORTS = {
    "EDDF": {"name": "Frankfurt", "lat": 50.0379, "lon": 8.5622, "tz": "Europe/Berlin"},
    "EDDK": {"name": "Cologne/Bonn", "lat": 50.8659, "lon": 7.1427, "tz": "Europe/Berlin"},
    "EDDL": {"name": "Düsseldorf", "lat": 51.2895, "lon": 6.7668, "tz": "Europe/Berlin"},
    "EDDM": {"name": "Munich", "lat": 48.3538, "lon": 11.7861, "tz": "Europe/Berlin"},
    "KSTL": {"name": "St. Louis", "lat": 38.7487, "lon": -90.3700, "tz": "America/Chicago"},
    "KORD": {"name": "Chicago", "lat": 41.9742, "lon": -87.9073, "tz": "America/Chicago"},
}

# buffers in minutes (from our D3)
APPROACH_BUFFER = 10
EXIT_BUFFER = 30
TERMINAL_BUFFER = 30
SAFETY_MARGIN = 10

SEARCH_BOX = 15.0  # degrees around the airport for the OpenSky request (about 1600 km)
CSV_PATH = "reports/leave_log.csv"


def ask_minutes(question, default, maximum):
    """Ask for a number of minutes. Enter = default. Asks again on wrong input."""
    while True:
        text = input(question).strip()
        if text == "":
            return default
        if text.isdigit() and int(text) <= maximum:
            return int(text)
        print("Please enter a number between 0 and " + str(maximum) + ".")


def ask_drive_time(airport):
    """Ask for the drive time. Enter = use a ZIP code instead."""
    while True:
        text = input("Drive time in minutes (or press Enter to use a ZIP code): ").strip()
        if text.isdigit():
            return int(text)
        if text != "":
            print("Please enter a whole number, for example 35.")
            continue

        # drive time from a ZIP code
        country = input("ZIP code country (US/DE): ").strip().upper()
        zip_code = input("ZIP code: ").strip()
        coords = zip_to_coords(zip_code, country)
        if coords is not None:
            minutes = drive_minutes(coords, (airport["lat"], airport["lon"]))
            if minutes is not None:
                print("Drive time: about " + str(minutes) + " minutes.")
                return minutes
        print("Could not get the drive time. Please type it in.")


def ask_input(airports):
    """Ask for the mode and all inputs. Returns a dictionary with the answers."""
    answers = {}

    # 1. mode
    while True:
        mode = input("Mode (pickup/departure): ").strip().lower()
        if mode == "pickup" or mode == "departure":
            break
        print("Please enter 'pickup' or 'departure'.")
    answers["mode"] = mode

    # 2. flight number (pickup only)
    if mode == "pickup":
        while True:
            callsign = to_callsign(input("Flight number: "), AIRLINES)
            if callsign is not None:
                break
            print("Unknown flight number. Use a format like 'LH 123'.")
        answers["flight"] = callsign

    # 3. airport
    while True:
        code = input("Airport (ICAO code): ").strip().upper()
        if code in airports:
            break
        print("Unknown airport. Choose one of: " + ", ".join(airports))
    answers["airport"] = code
    airport = airports[code]
    tz = ZoneInfo(airport["tz"])

    # 4. departure time (departure only)
    if mode == "departure":
        while True:
            text = input("Departure time (YYYY-MM-DD HH:MM): ").strip()
            try:
                departure = datetime.strptime(text, "%Y-%m-%d %H:%M")
            except ValueError:
                print("Wrong format. Example: 2026-11-28 14:35")
                continue
            departure = departure.replace(tzinfo=tz)
            if departure <= datetime.now(tz):
                print("That departure time is in the past.")
                continue
            break
        answers["departure"] = departure

    # 5. buffers and drive time
    if mode == "pickup":
        answers["buffer_min"] = ask_minutes(
            "Minutes from landing until the passenger is at the exit [30]: ", EXIT_BUFFER, 300)
    else:
        answers["buffer_min"] = ask_minutes(
            "Minutes at the terminal before departure [30]: ", TERMINAL_BUFFER, 300)
    answers["drive_min"] = ask_drive_time(airport)
    answers["safety_min"] = ask_minutes("Safety margin in minutes [10]: ", SAFETY_MARGIN, 120)

    return answers


def leave_time(target, drive_min, safety_min):
    """Target time minus drive time and safety margin."""
    return target - timedelta(minutes=drive_min + safety_min)


def show_time(moment, airport):
    """One time in the airport's zone and in the partner zone, e.g. '15:37 CET (08:37 CST)'."""
    local = moment.astimezone(ZoneInfo(airport["tz"]))
    if airport["tz"] == "Europe/Berlin":
        partner = moment.astimezone(ZoneInfo("America/Chicago"))
    else:
        partner = moment.astimezone(ZoneInfo("Europe/Berlin"))

    return local.strftime("%H:%M %Z") + " (" + partner.strftime("%H:%M %Z") + ")"


def format_summary(result):
    """Text for the user, every time in both time zones."""
    airport = AIRPORTS[result["airport"]]
    lines = []

    if result["mode"] == "pickup":
        lines.append(result["flight"] + " is " + str(round(result["distance_km"])) + " km from "
                     + airport["name"] + ", " + str(round(result["speed_ms"])) + " m/s.")
        lines.append("Estimated landing: " + show_time(result["landing"], airport))
        lines.append("Passenger at exit: " + show_time(result["target"], airport))
    else:
        lines.append("Departure: " + show_time(result["departure"], airport))
        lines.append("At the terminal by: " + show_time(result["target"], airport))

    lines.append("Leave at: " + show_time(result["leave"], airport))

    if result["mode"] == "pickup":
        lines.append("Estimate only, not an official arrival time.")
    return "\n".join(lines)


def append_csv(row, path):
    """Add one row to the CSV file. Writes the header first if the file is new."""
    folder = os.path.dirname(path)
    if folder != "":
        os.makedirs(folder, exist_ok=True)
    new_file = not os.path.exists(path)

    with open(path, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if new_file:
            writer.writerow(["time", "mode", "flight", "landing", "leave_time"])
        writer.writerow(row)


def main():
    """Run everything for the chosen mode."""
    answers = ask_input(AIRPORTS)
    airport = AIRPORTS[answers["airport"]]
    now = datetime.now(ZoneInfo(airport["tz"]))

    if answers["mode"] == "pickup":
        # ask OpenSky for all aircraft in a box around the airport
        lat = airport["lat"]
        lon = airport["lon"]
        box = (lat - SEARCH_BOX, lon - SEARCH_BOX, lat + SEARCH_BOX, lon + SEARCH_BOX)
        data = fetch_json(build_url(box))
        if data is None:
            return  # fetch_json already printed what went wrong

        # turn the lists into dictionaries and look for our flight
        states = []
        if data.get("states") is not None:
            for vector in data["states"]:
                aircraft = parse_state(vector)
                if aircraft is not None:
                    states.append(aircraft)

        flight = find_flight(states, answers["flight"])
        if flight is None:
            print("Not trackable yet. Check again in 15 minutes.")
            return
        if flight["on_ground"]:
            print("This flight has already landed.")
            return

        # estimate the landing time
        distance = haversine_km(flight["lat"], flight["lon"], lat, lon)
        landing = estimate_landing(distance, flight["velocity"], now)
        if landing is None:
            print("Speed unknown right now. Check again in 15 minutes.")
            return
        landing = landing + timedelta(minutes=APPROACH_BUFFER)
        target = landing + timedelta(minutes=answers["buffer_min"])

        result = {"mode": "pickup", "flight": answers["flight"], "airport": answers["airport"],
                  "distance_km": distance, "speed_ms": flight["velocity"],
                  "landing": landing, "target": target}
    else:
        # departure mode: no OpenSky request
        target = answers["departure"] - timedelta(minutes=answers["buffer_min"])
        result = {"mode": "departure", "flight": "", "airport": answers["airport"],
                  "departure": answers["departure"], "landing": None, "target": target}

    result["leave"] = leave_time(target, answers["drive_min"], answers["safety_min"])

    # output
    print()
    print(format_summary(result))

    # save one row to the CSV file
    landing_text = ""
    if result["landing"] is not None:
        landing_text = result["landing"].strftime("%Y-%m-%d %H:%M")
    row = [datetime.now().strftime("%Y-%m-%d %H:%M"), result["mode"], result["flight"],
           landing_text, result["leave"].strftime("%Y-%m-%d %H:%M")]
    append_csv(row, CSV_PATH)
    print("Saved to " + CSV_PATH)


if __name__ == "__main__":
    main()
