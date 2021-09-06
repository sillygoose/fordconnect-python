"""Code to interface with the FordPass Connect API as used in the FordPass app"""
# POST https://api.mps.ford.com/api//cevs/v2/chargelogs/retrieve

import logging
import sys
import requests

import version
import logfiles
from readconfig import read_config

from fordpass import Vehicle


_VEHICLECLIENT = None

_LOGGER = logging.getLogger("fordconnect")


def get_chargelogs():
    global _VEHICLECLIENT
    status = None
    tries = 3
    while tries > 0:
        try:
            status = _VEHICLECLIENT.chargelogs()
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
    _LOGGER.info(f"Ford Connect charge log utility {version.get_version()}")

    config = read_config()
    if not config:
        _LOGGER.error("Error processing YAML configuration - exiting")
        return

    _VEHICLECLIENT = Vehicle(
        username=config.fordconnect.vehicle.username,
        password=config.fordconnect.vehicle.password,
        vin=config.fordconnect.vehicle.vin,
    )
    chargeLogs = get_chargelogs().get("chargeLogs")
    _LOGGER.info(f"Charge logs:")
    for chargeLog in chargeLogs:
        _LOGGER.info(
            f"ID: {chargeLog.get('chargeId')}, Plug out time: {chargeLog.get('plugOutTime')}, Start Battery Level: {chargeLog.get('startBatteryLevel')}, End Battery Level: {chargeLog.get('endBatteryLevel')}, Location: {chargeLog.get('chargeLocation')}"
        )


if __name__ == "__main__":
    # make sure we can run this
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 8:
        main()
    else:
        print("python 3.8 or better required")