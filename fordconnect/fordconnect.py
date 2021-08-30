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

_GEOCLIENT = None
_VEHICLECLIENT = None
_MILES = True


# 'Fully open position'
# 'Btwn 10 % and 60 % open'
# 'Fully closed position'
def decode_windows(status):
    windowPosition = [
        status.get("windowPosition").get("driverWindowPosition").get("value"),
        status.get("windowPosition").get("passWindowPosition").get("value"),
        status.get("windowPosition").get("rearDriverWindowPos").get("value"),
        status.get("windowPosition").get("rearPassWindowPos").get("value"),
    ]
    if "Btwn 10 % and 60 % open" in windowPosition or "Fully open position" in windowPosition:
        logging.info(f"One or more windows are open")
    else:
        logging.info(f"All windows are closed")


# 'Closed'
# 'Ajar'
def decode_doors(status):
    doorStatus = [
        status.get("doorStatus").get("rightRearDoor").get("value"),
        status.get("doorStatus").get("leftRearDoor").get("value"),
        status.get("doorStatus").get("driverDoor").get("value"),
        status.get("doorStatus").get("passengerDoor").get("value"),
        status.get("doorStatus").get("hoodDoor").get("value"),
        status.get("doorStatus").get("tailgateDoor").get("value"),
        status.get("doorStatus").get("innerTailgateDoor").get("value"),
    ]
    if "Ajar" in doorStatus:
        logging.info(f"Door status is {doorStatus}")
    else:
        logging.info(f"All doors are closed")


def decode_ignition(status):
    ignitionStatus = status.get("ignitionStatus").get("value")
    logging.info(f"Ignition status is '{ignitionStatus}'")


def decode_charging(status):
    chargingStatus = status.get("chargingStatus").get("value")
    logging.info(f"Charging status is '{chargingStatus}'")


def decode_plug(status):
    plugStatus = status.get("plugStatus").get("value")
    plugState = "plugged in" if plugStatus else "not plugged in"
    logging.info(f"Plug status is {plugState}")


def decode_tpms(status):
    tirePressureStatus = "are good" if status.get("tirePressure").get("value") == "STATUS_GOOD" else "need checking"
    logging.info(f"Tire pressures {tirePressureStatus}")
    KPA_TO_PSI = 0.1450377
    tirePressures = [
        int(round(float(status.get("TPMS").get("leftFrontTirePressure").get("value")) * KPA_TO_PSI, 0)),
        int(round(float(status.get("TPMS").get("rightFrontTirePressure").get("value")) * KPA_TO_PSI, 0)),
        int(round(float(status.get("TPMS").get("outerLeftRearTirePressure").get("value")) * KPA_TO_PSI, 0)),
        int(round(float(status.get("TPMS").get("outerRightRearTirePressure").get("value")) * KPA_TO_PSI, 0)),
    ]
    logging.info(f"Tire pressures are {tirePressures}")


def decode_odometer(status):
    global _MILES
    odometer = float(status.get("odometer").get("value"))
    unit = "km"
    if _MILES:
        odometer = odometer * 0.6214
        unit = "miles"
    logging.info(f"Odometer reads {odometer:.1f} {unit}")


def decode_dte(status):
    global _MILES
    dte = float(status.get("elVehDTE").get("value"))
    unit = "km"
    if _MILES:
        dte = dte * 0.6214
        unit = "miles"
    logging.info(f"Estimated range is {dte:.0f} {unit}")


def decode_soc(status):
    soc = float(status.get("batteryFillLevel").get("value"))
    logging.info(f"Battery is at {soc:.0f}% of capacity")


def decode_locked(status):
    locked = status.get("lockStatus").get("value")
    logging.info(f"Car doors are '{locked}'")


def decode_preconditioning(status):
    remoteStartStatus = status.get("remoteStartStatus").get("value")
    if remoteStartStatus == 0:
        logging.info(f"Vehicle is not preconditioning")
    else:
        remoteStartDuration = int(status.get("remoteStart").get("remoteStartDuration"))
        remoteStartTime = int(status.get("remoteStart").get("remoteStartTime"))
        logging.info(f"Vehicle is preconditioning, time is {remoteStartTime} for duration {remoteStartDuration}")


def decode_location(status):
    global _GEOCLIENT
    locationInfo = _GEOCLIENT.reverse((status.get("gps").get("latitude"), status.get("gps").get("longitude")))
    nearestLocation = locationInfo.get("results")
    atLocation = nearestLocation[0]
    logging.info(f"Vehicle location is near {atLocation.get('formatted_address')}")


def decode(previous, current):
    print(f"{current}")


def main():
    """Set up and start FordConnect."""

    global _GEOCLIENT
    global _VEHICLECLIENT

    logfiles.create_application_log()
    logging.info(f"Ford Connect test utility {version.get_version()}")

    config = read_config()
    if not config:
        logging.error("Error processing YAML configuration - exiting")
        return

    _VEHICLECLIENT = Vehicle(
        username=config.fordconnect.vehicle.username,
        password=config.fordconnect.vehicle.password,
        vin=config.fordconnect.vehicle.vin,
    )
    currentStatus = _VEHICLECLIENT.status()

    _GEOCLIENT = GeocodioClient(config.geocodio.api_key)

    decode_windows(status=currentStatus)
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
                logging.info(f"Update detected at {currentModified}")

                # Figure out what changed
                decode(previous=previousStatus, current=currentStatus)

                # Update the previous status
                previousStatus = currentStatus

    except Exception as e:
        logging.error(f"Unexpected exception: {e}")


if __name__ == "__main__":
    # make sure we can run multisma2
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 8:
        main()
    else:
        print("python 3.8 or better required")
