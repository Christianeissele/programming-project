# api_client.py
# my part of the project (Ihsan)
# this file gets the data from the internet
# fetch_json is from the starter code of the project brief

import json
import urllib.error
import urllib.request

# the address of the opensky api
BASE_URL = "https://opensky-network.org/api/states/all"


def build_url(box):
    """makes the url for opensky. box = (lamin, lomin, lamax, lomax)"""
    lamin = box[0]
    lomin = box[1]
    lamax = box[2]
    lomax = box[3]
    url = BASE_URL + "?lamin=" + str(lamin) + "&lomin=" + str(lomin)
    url = url + "&lamax=" + str(lamax) + "&lomax=" + str(lomax)
    return url


def fetch_json(url):
    """gets the json from the url. gives back None if something goes wrong"""
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        print("The service answered with an error:", error.code)
    except urllib.error.URLError:
        print("No connection to the service. Check your internet access.")
    except json.JSONDecodeError:
        print("The service sent data that is not valid JSON.")
    return None


def zip_to_coords(zip_code, country):
    """gives back (lat, lon) of a zip code or None"""
    url = "https://api.zippopotam.us/" + country.lower() + "/" + zip_code
    data = fetch_json(url)
    if data is None:
        return None
    try:
        # the api gives a list of places, we take the first one
        place = data["places"][0]
        lat = float(place["latitude"])
        lon = float(place["longitude"])
        return (lat, lon)
    except (KeyError, IndexError):
        print("Could not find the zip code.")
        return None


def drive_minutes(start, end):
    """gives back how many minutes you drive from start to end, or None"""
    start_lat = start[0]
    start_lon = start[1]
    end_lat = end[0]
    end_lon = end[1]
    # careful: osrm wants lon first and then lat!
    url = "https://router.project-osrm.org/route/v1/driving/"
    url = url + str(start_lon) + "," + str(start_lat) + ";" + str(end_lon) + "," + str(end_lat)
    data = fetch_json(url)
    if data is None:
        return None
    try:
        seconds = data["routes"][0]["duration"]
        minutes = round(seconds / 60)
        return minutes
    except (KeyError, IndexError):
        print("Could not find a route.")
        return None


def save_sample(data, path):
    """saves the data in a json file so we can test without internet"""
    file = open(path, "w")
    json.dump(data, file)
    file.close()


def load_sample(path):
    """loads the data from the json file again"""
    file = open(path, "r")
    data = json.load(file)
    file.close()
    return data