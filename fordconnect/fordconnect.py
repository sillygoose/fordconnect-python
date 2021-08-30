"""Code to interface with the Ford Connect API as used in the FordPass app"""

import logging
import sys
import time
from datetime import datetime

import version
import logfiles
from readconfig import read_config

from fordpass import Vehicle


_LOGGER = logging.getLogger()


def main():
    """Set up and start FordConnect."""

    logfiles.create_application_log()
    _LOGGER.info(f"Ford Connect test utility {version.get_version()}")

    config = read_config()
    if not config:
        _LOGGER.error("Error processing YAML configuration - exiting")
        return

    try:
        params = config.fordconnect.vehicle
        vehicle = Vehicle(username=params.username, password=params.password, vin=params.vin)
        previousStatus = vehicle.status()
        limit = 10
        passes = 0
        while True:
            time.sleep(30)
            currentStatus = vehicle.status()
            passes += 1
            if passes > limit:
                break

            previousModified = datetime.strptime(previousStatus.get("lastModifiedDate"), "%m-%d-%Y %H:%M:%S")
            currentModified = datetime.strptime(currentStatus.get("lastModifiedDate"), "%m-%d-%Y %H:%M:%S")
            if currentModified > previousModified:
                _LOGGER.info(f"Update detected at {currentModified}")

                # Figure out what changed

                # Try geocoding

                previousStatus = currentStatus

            pass
    except Exception as e:
        _LOGGER.error(f"Unexpected exception: {e}")


if __name__ == "__main__":
    # make sure we can run multisma2
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 7:
        main()
    else:
        print("python 3.7 or better required")
