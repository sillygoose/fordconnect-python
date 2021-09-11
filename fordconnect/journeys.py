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

# journeys use meters per second, meters, and meters, adjust accordingly when other units are used
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


def display_detailed_journey(
    journey, showReverseAddress=False, showElevation=False, showLocations=False, showEvents=False
):
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

    deltaElevation = 0
    if showElevation:
        startingElevation = usgs_alt(lat=start.get("latitude"), lon=start.get("longitude"))
        endingElevation = usgs_alt(lat=end.get("latitude"), lon=end.get("longitude"))
        deltaElevation = endingElevation - startingElevation

    _LOGGER.info(
        f"Detailed journey {journey.get('journeyID')} on {journeyDate.strftime('%Y-%m-%d')} at {journeyDate.strftime('%H:%M')}"
    )
    _LOGGER.info(
        f"Duration: {hours:.0f} hour(s), {minutes:.0f} minute(s) and {seconds:.0f} second(s), "
        f"Distance: {_CONVERSIONS[_MILES].get('distance')*distance:.2f} {_UNITS[_MILES].get('distance')}, "
        f"Average Speed: {_CONVERSIONS[_MILES].get('speed')*avgSpeed:.2f} {_UNITS[_MILES].get('speed')}, "
        f"Elevation change: {_CONVERSIONS[_MILES].get('elevation')*deltaElevation:.0f} {_UNITS[_MILES].get('elevation')}"
    )

    if showReverseAddress:
        startingLocationInfo = _GEOCLIENT.reverse((start.get("latitude"), start.get("longitude")))
        endingLocationInfo = _GEOCLIENT.reverse((end.get("latitude"), end.get("longitude")))
        _LOGGER.info(f"From {get_street_town(startingLocationInfo)} to {get_street_town(endingLocationInfo)}")
    else:
        _LOGGER.info(
            f"From ({start.get('latitude'):.03f}, {start.get('longitude'):.03f}) to "
            f"({end.get('latitude'):.03f}, {end.get('longitude'):.03f})"
        )

    if showLocations:
        locations = details.get("value").get("locations")
        if len(locations):
            _LOGGER.info(f"{len(locations)} locations logged")
            for location in locations:
                _LOGGER.info(
                    f"Location: ({location.get('latitude'):.3f}, {location.get('longitude'):.3f}), "
                    f"Time: {datetime.fromtimestamp(location.get('timestamp')).strftime('%H:%M:%S')}, "
                    f"Speed: {_CONVERSIONS[_MILES].get('speed')*location.get('speed'):.2f} {_UNITS[_MILES].get('speed')}"
                )

    if showEvents:
        events = details.get("value").get("events")
        if len(events):
            _LOGGER.info(f"{len(events)} events logged")
            for event in events:
                _LOGGER.info(
                    f"Location: ({event.get('latitude'):.3f}, {event.get('longitude'):.3f}), "
                    f"Time: {datetime.fromtimestamp(event.get('timestamp')).strftime('%H:%M:%S')}, "
                    f"Description: {event.get('description')}"
                )


def display_journey(journey, showReverseAddress=False, showElevation=False, showLocations=False):
    global _GEOCLIENT, _MILES, _UNITS, _CONVERSIONS

    start = journey.get("start")
    end = journey.get("end")
    duration = end.get("timestamp") - start.get("timestamp")
    hours = duration // 3600
    minutes = (duration % 3600) // 60
    seconds = duration % 60
    journeyDate = datetime.fromtimestamp(start.get("timestamp"))

    deltaElevation = 0
    if showElevation:
        startingElevation = usgs_alt(lat=start.get("latitude"), lon=start.get("longitude"))
        endingElevation = usgs_alt(lat=end.get("latitude"), lon=end.get("longitude"))
        deltaElevation = endingElevation - startingElevation

    distance = journey.get("distance")
    avgSpeed = journey.get("avgSpeed")

    _LOGGER.info(
        f"Journey {journey.get('journeyID')} on {journeyDate.strftime('%Y-%m-%d')} at {journeyDate.strftime('%H:%M')}"
    )
    _LOGGER.info(
        f"Duration: {hours:.0f} hour(s), {minutes:.0f} minute(s) and {seconds:.0f} second(s), "
        f"Distance: {_CONVERSIONS[_MILES].get('distance')*distance:.2f} {_UNITS[_MILES].get('distance')}, "
        f"Average Speed: {_CONVERSIONS[_MILES].get('speed')*avgSpeed:.2f} {_UNITS[_MILES].get('speed')}, "
        f"Elevation change: {_CONVERSIONS[_MILES].get('elevation')*deltaElevation:.0f} {_UNITS[_MILES].get('elevation')}"
    )

    if showReverseAddress:
        startingLocationInfo = _GEOCLIENT.reverse((start.get("latitude"), start.get("longitude")))
        endingLocationInfo = _GEOCLIENT.reverse((end.get("latitude"), end.get("longitude")))
        _LOGGER.info(f"From {get_street_town(startingLocationInfo)} to {get_street_town(endingLocationInfo)}")
    else:
        _LOGGER.info(
            f"From ({start.get('latitude'):.03f}, {start.get('longitude'):.03f}) to "
            f"({end.get('latitude'):.03f}, {end.get('longitude'):.03f})"
        )

    if showLocations:
        locations = journey.get("locations")
        _LOGGER.info(f"{len(locations)} locations logged")
        for location in locations:
            _LOGGER.info(
                f"Location: ({location.get('latitude'):.3f}, {location.get('longitude'):.3f}), "
                f"Time: {datetime.fromtimestamp(location.get('timestamp')).strftime('%H:%M:%S')}, "
                f"Speed: {_CONVERSIONS[_MILES].get('speed')*location.get('speed'):.2f} {_UNITS[_MILES].get('speed')}, "
            )


def display_journeys(
    journeys,
    showMostRecentJourney=False,
    showDetailedJourney=False,
    showElevation=False,
    showReverseAddress=False,
    showLocations=False,
    showEvents=False,
):
    """Display a list of journeys or just the most recent journey"""
    if showMostRecentJourney:
        newestJourney = None
        for journey in journeys:
            if newestJourney:
                if journey.get("start").get("timestamp") > newestJourney.get("start").get("timestamp"):
                    newestJourney = journey
            else:
                newestJourney = journey
        _LOGGER.info(f"Most recent logged journey")
        display_journey(newestJourney, showElevation, showReverseAddress, showLocations)
        if showDetailedJourney:
            _LOGGER.info(f"")
            display_detailed_journey(newestJourney, showElevation, showReverseAddress, showLocations, showEvents)
        return

    _LOGGER.info(f"List of all journeys")
    for journey in journeys:
        display_journey(journey, showElevation=False, showReverseAddress=False, showLocations=False)
        _LOGGER.info(f"")


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

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=2)
    journeys = get_journeys(start=int(start_date.timestamp()), end=int(end_date.timestamp())).get("value")
    display_journeys(
        journeys=journeys,
        showMostRecentJourney=True,
        showDetailedJourney=True,
        showElevation=True,
        showReverseAddress=True,
        showLocations=False,
        showEvents=False,
    )

    _LOGGER.info(f"")
    _LOGGER.info(f"Display a random journey in the time period")
    display_journey(journey=journeys[random.randint(0, len(journeys) - 1)])


if __name__ == "__main__":
    # make sure we can run this
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 9:
        main()
    else:
        print("python 3.9 or newer required")
