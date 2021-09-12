"""Code to interface with the FordPass Connect API as used in the FordPass app"""
# POST https://api.mps.ford.com/api//cevs/v1/triplogs/retrieve

import logging
import sys
import requests

import version
import logfiles
from readconfig import read_config

from fordpass import Vehicle


_VEHICLECLIENT = None

_LOGGER = logging.getLogger("fordconnect")


def get_triplogs():
    global _VEHICLECLIENT
    status = None
    tries = 3
    while tries > 0:
        try:
            status = _VEHICLECLIENT.triplogs()
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
    _LOGGER.info(f"Ford Connect trip log utility {version.get_version()}")

    config = read_config()
    if not config:
        _LOGGER.error("Error processing YAML configuration - exiting")
        return

    fordconnect = config.get('fordconnect')
    _VEHICLECLIENT = Vehicle(
        username=fordconnect.get('username'),
        password=fordconnect.get('password'),
        vin=fordconnect.get('vin'),
    )

    tripLogs = get_triplogs()
    _LOGGER.info(f"Trip logs: {tripLogs}")


if __name__ == "__main__":
    # make sure we can run this
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 9:
        main()
    else:
        print("python 3.9 or newer required")
