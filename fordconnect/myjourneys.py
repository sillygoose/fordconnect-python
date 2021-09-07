"""Code to interface with the FordPass Connect API as used in the FordPass app"""
# GET https://api.mps.ford.com/api/journey-info/v1/journeys?endDate=sec_ts&clientVersion=iOS3.29.0&vins=MYVIN&countryCode=USA&startDate-sects
# GET https://api.mps.ford.com/api/journey-info/v1/journeys?endDate=sec_ts&clientVersion=iOS3.29.0&vins=MYVIN&countryCode=USA&startDate-sects

# Detailed journey info
# GET https://api.mps.ford.com/api/journey-info/v1/journey/details/<journeyID>?clientVersion=iOS3.29.0&vin=<vin>


import logging
import sys
import requests
import random

import version
import logfiles
from readconfig import read_config

from datetime import timedelta
from datetime import datetime

from fordpass import Vehicle
from geocodio import GeocodioClient
from usgs_elevation import usgs_alt


_VEHICLECLIENT = None
_GEOCLIENT = None

_LOGGER = logging.getLogger("fordconnect")

_MILES = True

_UNITS = [
    {"speed": "kph", "distance": "km", "elevation": "m"},
    {"speed": "mph", "distance": "miles", "elevation": "ft"},
]
_CONVERSIONS = [
    {"speed": 3.6, "distance": 0.001, "elevation": 1.0},
    {"speed": 3.6 * 0.6214, "distance": 0.001 * 0.6214, "elevation": 3.2808},
]


def get_journeys(start, end):

    global _VEHICLECLIENT

    status = None
    tries = 3
    while tries > 0:
        try:
            status = _VEHICLECLIENT.journeys(start=start, end=end)
            break
        except requests.ConnectionError:
            tries -= 1
            # _LOGGER.info(f"request.get() timed out, {tries} remaining")
            if tries == 0:
                _LOGGER.error(f"FordPass Connect API unavailable")
                raise
            continue
        except Exception as e:
            _LOGGER.error(f"Unexpected exception: {e}")
            break
    return status


def get_journey_details(id):

    global _VEHICLECLIENT

    status = None
    tries = 3
    while tries > 0:
        try:
            status = _VEHICLECLIENT.journey_details(id=id)
            break
        except requests.ConnectionError:
            tries -= 1
            # _LOGGER.info(f"request.get() timed out, {tries} remaining")
            if tries == 0:
                _LOGGER.error(f"FordPass Connect API unavailable")
                raise
            continue
        except Exception as e:
            _LOGGER.error(f"Unexpected exception: {e}")
            break
    return status


def get_street_town(location):
    components = location["results"][0]["address_components"]
    return f"'{components.get('formatted_street', '???')}, {components.get('city', '???')}'"


def display_journey_details(journey):
    global _GEOCLIENT, _MILES, _UNITS, _CONVERSIONS

    journeyID = journey.get("journeyID")
    details = get_journey_details(id=journeyID)

    summary = details.get("value").get("summary")
    distance = summary.get("distance")
    avgSpeed = summary.get("avgSpeed")

    start = details.get("value").get("start")
    end = details.get("value").get("end")
    duration = end.get("timestamp") - start.get("timestamp")
    hours = duration // 3600
    minutes = (duration % 3600) // 60
    seconds = duration % 60
    journeyDate = datetime.fromtimestamp(start.get("timestamp"))

    startingElevation = usgs_alt(lat=start.get("latitude"), lon=start.get("longitude"))
    endingElevation = usgs_alt(lat=end.get("latitude"), lon=end.get("longitude"))
    deltaElevation = endingElevation - startingElevation

    startingLocationInfo = _GEOCLIENT.reverse((start.get("latitude"), start.get("longitude")))
    endingLocationInfo = _GEOCLIENT.reverse((end.get("latitude"), end.get("longitude")))

    _LOGGER.info(f"")
    _LOGGER.info(f"Detailed Journey view for {journeyID}")
    _LOGGER.info(
        f"From {get_street_town(startingLocationInfo)} to {get_street_town(endingLocationInfo)} on {journeyDate.strftime('%m-%d-%y %H:%M')}"
    )

    _LOGGER.info(
        f"Duration: {hours:02.0f}:{minutes:02.0f}:{seconds:02.0f}, "
        f"Distance: {_CONVERSIONS[_MILES].get('distance')*distance:.2f} {_UNITS[_MILES].get('distance')}, "
        f"Average Speed: {_CONVERSIONS[_MILES].get('speed')*avgSpeed:.2f} {_UNITS[_MILES].get('speed')}, "
        f"Elevation change: {_CONVERSIONS[_MILES].get('elevation')*deltaElevation:.0f} {_UNITS[_MILES].get('elevation')}"
    )

    locations = details.get("value").get("locations")
    if len(locations):
        _LOGGER.info(f"{len(locations)} locations logged")
        for location in locations:
            _LOGGER.info(
                f"Location: ({location.get('latitude'):.3f}, {location.get('longitude'):.3f}), "
                f"Time: {datetime.fromtimestamp(location.get('timestamp')).strftime('%H:%M:%S')}, "
                f"Speed: {_CONVERSIONS[_MILES].get('speed')*location.get('speed'):.2f} {_UNITS[_MILES].get('speed')}"
            )

    events = details.get("value").get("events")
    if len(events):
        _LOGGER.info(f"{len(events)} events logged")
        for event in events:
            _LOGGER.info(
                f"Location: ({event.get('latitude'):.3f}, {event.get('longitude'):.3f}), "
                f"Time: {datetime.fromtimestamp(event.get('timestamp')).strftime('%H:%M:%S')}, "
                f"Description: {event.get('description')}"
            )


def display_journey(journey):
    global _GEOCLIENT, _MILES, _UNITS, _CONVERSIONS

    start = journey.get("start")
    end = journey.get("end")
    duration = end.get("timestamp") - start.get("timestamp")
    hours = duration // 3600
    minutes = (duration % 3600) // 60
    seconds = duration % 60
    journeyDate = datetime.fromtimestamp(start.get("timestamp"))

    startingElevation = usgs_alt(lat=start.get("latitude"), lon=start.get("longitude"))
    endingElevation = usgs_alt(lat=end.get("latitude"), lon=end.get("longitude"))
    deltaElevation = endingElevation - startingElevation

    distance = journey.get("distance")
    avgSpeed = journey.get("avgSpeed")

    startingLocationInfo = _GEOCLIENT.reverse((start.get("latitude"), start.get("longitude")))
    endingLocationInfo = _GEOCLIENT.reverse((end.get("latitude"), end.get("longitude")))

    _LOGGER.info(f"")
    _LOGGER.info(f"Journey {journey.get('journeyID')}")
    _LOGGER.info(
        f"Date, Duration: {journeyDate.strftime('%m-%d-%y %H:%M')}, {hours:02.0f}:{minutes:02.0f}:{seconds:02.0f}, "
        f"Distance: {_CONVERSIONS[_MILES].get('distance')*distance:.2f} {_UNITS[_MILES].get('distance')}, "
        f"Average Speed: {_CONVERSIONS[_MILES].get('speed')*avgSpeed:.2f} {_UNITS[_MILES].get('speed')}, "
        f"Elevation change: {_CONVERSIONS[_MILES].get('elevation')*deltaElevation:.0f} {_UNITS[_MILES].get('elevation')}"
    )
    _LOGGER.info(
        f"From {get_street_town(startingLocationInfo)} to {get_street_town(endingLocationInfo)} on {journeyDate.strftime('%d-%m-%y %H:%M')}"
    )

    locations = journey.get("locations")
    _LOGGER.info(f"{len(locations)} locations logged")
    for location in locations:
        _LOGGER.info(
            f"Location: ({location.get('latitude'):.3f}, {location.get('longitude'):.3f}), "
            f"Time: {datetime.fromtimestamp(location.get('timestamp')).strftime('%H:%M:%S')}, "
            f"Speed: {_CONVERSIONS[_MILES].get('speed')*location.get('speed'):.2f} {_UNITS[_MILES].get('speed')}, "
        )


def main():
    """Set up and start FordPass Connect."""

    global _VEHICLECLIENT, _GEOCLIENT, _MILES

    logfiles.create_application_log(_LOGGER)
    _LOGGER.info(f"Ford Connect journey utility {version.get_version()}")

    config = read_config()
    if not config:
        _LOGGER.error("Error processing YAML configuration - exiting")
        return

    _VEHICLECLIENT = Vehicle(
        username=config.fordconnect.vehicle.username,
        password=config.fordconnect.vehicle.password,
        vin=config.fordconnect.vehicle.vin,
    )
    _GEOCLIENT = GeocodioClient(config.geocodio.api_key)

    week_ago = timedelta(weeks=1)
    end_date = datetime.now()
    start_date = end_date - week_ago
    journeys = get_journeys(start=int(start_date.timestamp()), end=int(end_date.timestamp()))

    journeyList = journeys.get("value")
    randomJourney = random.randint(0, len(journeyList) - 1)
    display_journey(journey=journeyList[randomJourney])
    display_journey_details(journey=journeyList[randomJourney])


if __name__ == "__main__":
    # make sure we can run this
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 8:
        main()
    else:
        print("python 3.8 or better required")
