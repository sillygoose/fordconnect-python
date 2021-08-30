"""Code to interface with the Ford Connect API as used in the FordPass app"""

import logging
import sys
import time
from datetime import datetime

import version
import logfiles
from readconfig import read_config

from fordpass import Vehicle
from geocodio import GeocodioClient

_LOGGER = logging.getLogger()
_GEOCLIENT = None
_VEHICLECLIENT = None
_MILES = True


def decode_doors(status):
    rightRearDoor = status.get("doorStatus").get("rightRearDoor").get("value")
    leftRearDoor = status.get("doorStatus").get("leftRearDoor").get("value")
    driverDoor = status.get("doorStatus").get("driverDoor").get("value")
    passengerDoor = status.get("doorStatus").get("passengerDoor").get("value")
    hoodDoor = status.get("doorStatus").get("hoodDoor").get("value")
    tailgateDoor = status.get("doorStatus").get("tailgateDoor").get("value")
    innerTailgateDoor = status.get("doorStatus").get("innerTailgateDoor").get("value")
    _LOGGER.info(f"Door status is {driverDoor}")


def decode_ignition(status):
    ignitionStatus = status.get("ignitionStatus").get("value")
    _LOGGER.info(f"Ignition status is {ignitionStatus}")


def decode_charging(status):
    chargingStatus = status.get("plugStatus").get("value")
    _LOGGER.info(f"Charging status {chargingStatus}")


def decode_plug(status):
    plugStatus = status.get("plugStatus").get("value")
    _LOGGER.info(f"Plug status {plugStatus}")


def decode_tpms(status):
    tirePressureStatus = "are good" if status.get("tirePressure").get("value") == "STATUS_GOOD" else "need checking"
    _LOGGER.info(f"Tire pressures {tirePressureStatus}")


def decode_odometer(status):
    global _MILES
    odometer = float(status.get("odometer").get("value"))
    unit = "kms"
    if _MILES:
        odometer = odometer * 0.6214
        unit = "miles"
    _LOGGER.info(f"Odometer reads {odometer:.1f} {unit}")


def decode_dte(status):
    global _MILES
    dte = float(status.get("elVehDTE").get("value"))
    unit = "kms"
    if _MILES:
        dte = dte * 0.6214
        unit = "miles"
    _LOGGER.info(f"Estimated range is {dte:.0f} {unit}")


def decode_soc(status):
    soc = float(status.get("batteryFillLevel").get("value"))
    _LOGGER.info(f"Battery is at {soc:.0f}% of capacity")


def decode_locked(status):
    locked = status.get("lockStatus").get("value")
    _LOGGER.info(f"Car doors are {locked}")


def decode_preconditioning(status):
    remoteStartStatus = status.get("remoteStartStatus").get("value")
    if remoteStartStatus == 0:
        _LOGGER.info(f"Vehicle is not preconditioning")
    else:
        remoteStartDuration = int(status.get("remoteStart").get("remoteStartDuration"))
        remoteStartTime = int(status.get("remoteStart").get("remoteStartTime"))
        _LOGGER.info(f"Vehicle is preconditioning, time is {remoteStartTime} for duration {remoteStartDuration}")


def decode_location(status):
    global _GEOCLIENT
    locationInfo = _GEOCLIENT.reverse((status.get("gps").get("latitude"), status.get("gps").get("longitude")))
    nearestLocation = locationInfo.get("results")
    atLocation = nearestLocation[0]
    _LOGGER.info(f"Vehicle location is near {atLocation.get('formatted_address')}")


def decode(previous, current):
    print(f"{current}")


def main():
    """Set up and start FordConnect."""

    global _GEOCLIENT
    global _VEHICLECLIENT

    logfiles.create_application_log()
    _LOGGER.info(f"Ford Connect test utility {version.get_version()}")

    config = read_config()
    if not config:
        _LOGGER.error("Error processing YAML configuration - exiting")
        return

    _VEHICLECLIENT = Vehicle(
        username=config.fordconnect.vehicle.username,
        password=config.fordconnect.vehicle.password,
        vin=config.fordconnect.vehicle.vin,
    )
    currentStatus = _VEHICLECLIENT.status()

    _GEOCLIENT = GeocodioClient(config.geocodio.api_key)

    decode_doors(status=currentStatus)
    decode_ignition(status=currentStatus)
    decode_plug(status=currentStatus)
    decode_charging(status=currentStatus)
    decode_preconditioning(status=currentStatus)
    decode_odometer(status=currentStatus)
    decode_locked(status=currentStatus)
    decode_dte(status=currentStatus)
    decode_soc(status=currentStatus)
    decode_tpms(status=currentStatus)
    decode_location(status=currentStatus)

    previousStatus = currentStatus
    try:
        limit = 10
        passes = 0
        while True:
            time.sleep(5)
            currentStatus = _VEHICLECLIENT.status()
            passes += 1
            if passes > limit:
                break

            previousModified = datetime.strptime(previousStatus.get("lastModifiedDate"), "%m-%d-%Y %H:%M:%S")
            currentModified = datetime.strptime(currentStatus.get("lastModifiedDate"), "%m-%d-%Y %H:%M:%S")
            if currentModified > previousModified:
                _LOGGER.info(f"Update detected at {currentModified}")

                # Figure out what changed
                decode(previous=previousStatus, current=currentStatus)

                # Update the previous status
                previousStatus = currentStatus

    except Exception as e:
        _LOGGER.error(f"Unexpected exception: {e}")


if __name__ == "__main__":
    # make sure we can run multisma2
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 7:
        main()
    else:
        print("python 3.7 or better required")
