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


_VEHICLECLIENT = None

_LOGGER = logging.getLogger("fordconnect")


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

    global _VEHICLECLIENT

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

    week_ago = timedelta(weeks=1)
    end_date = datetime.now()
    start_date = end_date - week_ago
    journeys = get_journeys(start=int(start_date.timestamp()), end=int(end_date.timestamp()))
    valueKey = journeys.get("value")
    for journey in valueKey:
        _LOGGER.info(
            f"Journey {journey.get('journeyID')}: {journey.get('duration')}/{journey.get('distance')}/{journey.get('avgSpeed')}/{journey.get('start')}/{journey.get('end')}"
        )


if __name__ == "__main__":
    # make sure we can run this
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 8:
        main()
    else:
        print("python 3.8 or better required")
