"""Code to interface with the FordPass Connect API as used in the FordPass app"""
# GET https://api.mps.ford.com/api/journey-info/v1/journeys?endDate=sec_ts&clientVersion=iOS3.29.0&vins=MYVIN&countryCode=USA&startDate-sects
# GET https://api.mps.ford.com/api/journey-info/v1/journeys?endDate=sec_ts&clientVersion=iOS3.29.0&vins=MYVIN&countryCode=USA&startDate-sects

# Detailed journey info
# GET https://api.mps.ford.com/api/journey-info/v1/journey/details/<journeyID>?clientVersion=iOS3.29.0&vin=<vin>


import logging
import sys
import requests

import version
import logfiles
from readconfig import read_config

from datetime import timedelta
from datetime import datetime

from fordpass import Vehicle
from geocodio import GeocodioClient


_VEHICLECLIENT = None
_GEOCLIENT = None

_LOGGER = logging.getLogger("fordconnect")

_MILES = True


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
    for journey in journeys.get("value"):
        _LOGGER.info(f"Journey {journey.get('journeyID')}")

        startingAt = journey.get("start")
        endingAt = journey.get("end")

        startTime = datetime.fromtimestamp(startingAt.get("timestamp"))
        endTime = datetime.fromtimestamp(endingAt.get("timestamp"))
        duration = endTime - startTime
        hours = duration.seconds // 3600
        minutes = (duration.seconds // 60) % 60
        _LOGGER.info(
            f"From {startTime.date()} {startTime.time()} to {endTime.date()} {endTime.time()}, {hours} hours, {minutes} minutes"
        )

        distance = journey.get("distance") / 1000
        unit = "km"
        if _MILES:
            distance = distance * 0.6214
            unit = "miles"
        _LOGGER.info(f"Distance {distance:.2f} {unit}")

        avgSpeed = 3600 / 1000 * journey.get("avgSpeed")
        unit = "kph"
        if _MILES:
            avgSpeed = avgSpeed * 0.6214
            unit = "mph"
        _LOGGER.info(f"Average Speed {avgSpeed:.2f} {unit}")

        locationInfo = _GEOCLIENT.reverse((startingAt.get("latitude"), startingAt.get("longitude")))
        nearestLocation = locationInfo.get("results")
        startingLocation = nearestLocation[0]

        locationInfo = _GEOCLIENT.reverse((endingAt.get("latitude"), endingAt.get("longitude")))
        nearestLocation = locationInfo.get("results")
        endingLocation = nearestLocation[0]

        _LOGGER.info(f"From {startingLocation.get('formatted_address')} to {endingLocation.get('formatted_address')}")
        for location in journey.get("locations"):
            locationTime = datetime.fromtimestamp(location.get("timestamp"))

            speed = 3600 / 1000 * location.get("speed")
            unit = "kph"
            if _MILES:
                speed = speed * 0.6214
                unit = "mph"

            locationInfo = _GEOCLIENT.reverse((location.get("latitude"), location.get("longitude")))
            nearestLocation = locationInfo.get("results")
            spotLocation = nearestLocation[0]

            _LOGGER.info(
                f"{locationTime.date()} {locationTime.time()}, speed {speed:.2f} {unit}, {spotLocation.get('formatted_address')}"
            )
            pass

        pass


if __name__ == "__main__":
    # make sure we can run this
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 8:
        main()
    else:
        print("python 3.8 or better required")
