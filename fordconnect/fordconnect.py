"""Code to interface with the FordPass Connect API as used in the FordPass app"""

import logging
import sys
import time
from datetime import datetime
import requests

import version
import logfiles
from readconfig import read_config

from fordpass import Vehicle
from geocodio import GeocodioClient
from abrp import AbrpClient


_VEHICLECLIENT = None
_GEOCLIENT = None
_ABRPCLIENT = None

_MILES = True
_EXTENDED = True
_PSI = True

_LOGGER = logging.getLogger("fordconnect")


def last_status_update(status):
    return datetime.strptime(status.get("lastModifiedDate"), "%m-%d-%Y %H:%M:%S")


def server_time(status):
    return datetime.strptime(status.get("serverTime"), "%m-%d-%Y %H:%M:%S")


def time_since_update(status):
    return server_time(status) - last_status_update(status)


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
        _LOGGER.info(f"One or more windows are open")
    else:
        _LOGGER.info(f"All windows are closed")


# 'Closed', 'Ajar'
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
        _LOGGER.info(f"Door status is {doorStatus}")
    else:
        _LOGGER.info(f"All doors are closed")


def decode_lastupdate(status):
    _LOGGER.info(f"Last modified {last_status_update(status)}, time since update {time_since_update(status)}")


# 'Off', 'Start', 'Run'
def decode_ignition(status):
    ignitionStatus = status.get("ignitionStatus").get("value")
    _LOGGER.info(f"Ignition status is '{ignitionStatus}'")


# 'NotReady', 'ChargingAC', 'ChargeTargetReached'
def decode_charging(status):
    chargingStatus = status.get("chargingStatus").get("value")
    _LOGGER.info(f"Charging status is '{chargingStatus}'")


# 0 - Not plugged in, 1 - Plugged in
def decode_plug(status):
    plugStatus = status.get("plugStatus").get("value")
    plugState = "plugged in" if plugStatus else "not plugged in"
    _LOGGER.info(f"Plug status is {plugState}")


def decode_tpms(status):
    # tirePressureStatus = "are good" if status.get("tirePressure").get("value") == "STATUS_GOOD" else "need checking"
    # _LOGGER.info(f"Tire pressures {tirePressureStatus}")
    global _PSI
    adjustKPA = 0.1450377 if _PSI else 1.0
    tirePressures = [
        int(round(float(status.get("TPMS").get("leftFrontTirePressure").get("value")) * adjustKPA, 0)),
        int(round(float(status.get("TPMS").get("rightFrontTirePressure").get("value")) * adjustKPA, 0)),
        int(round(float(status.get("TPMS").get("outerLeftRearTirePressure").get("value")) * adjustKPA, 0)),
        int(round(float(status.get("TPMS").get("outerRightRearTirePressure").get("value")) * adjustKPA, 0)),
    ]
    _LOGGER.info(f"Tire pressures are {tirePressures}")


def decode_odometer(status):
    global _MILES
    odometer = float(status.get("odometer").get("value"))
    unit = "km"
    if _MILES:
        odometer = odometer * 0.6214
        unit = "miles"
    _LOGGER.info(f"Odometer reads {odometer:.1f} {unit}")


def decode_dte(status):
    global _MILES
    dte = float(status.get("elVehDTE").get("value"))
    unit = "km"
    if _MILES:
        dte = dte * 0.6214
        unit = "miles"
    _LOGGER.info(f"Estimated range is {dte:.0f} {unit}")


def decode_soc(status):
    soc = float(status.get("batteryFillLevel").get("value"))
    _LOGGER.info(f"Battery is at {soc:.0f}% of capacity")


# 'LOCKED', 'UNLOCKED'
def decode_locked(status):
    locked = status.get("lockStatus").get("value")
    _LOGGER.info(f"Car doors are '{locked}'")


# 'NOTSET', 'SET', 'ACTIVE'
def decode_alarm(status):
    alarm = status.get("alarm").get("value")
    _LOGGER.info(f"Alarm is '{alarm}'")


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


def differences(previous, current):
    global _PSI
    diffs = {}

    # log modified times
    diffs["lastModifiedDate"] = previous.get("lastModifiedDate") + "/" + current.get("lastModifiedDate")
    # ignitionStatus
    if previous.get("ignitionStatus").get("value") != current.get("ignitionStatus").get("value"):
        diffs["ignitionStatus"] = current.get("ignitionStatus").get("value")
    # odometer
    if previous.get("odometer").get("value") != current.get("odometer").get("value"):
        diffs["odometer"] = current.get("odometer").get("value")
    # gps
    if previous.get("gps").get("latitude") != current.get("gps").get("latitude"):
        diffs["latitude"] = current.get("gps").get("latitude")
        diffs["longitude"] = current.get("gps").get("longitude")
    if previous.get("gps").get("longitude") != current.get("gps").get("longitude"):
        diffs["latitude"] = current.get("gps").get("latitude")
        diffs["longitude"] = current.get("gps").get("longitude")
    # lockStatus
    if previous.get("lockStatus").get("value") != current.get("lockStatus").get("value"):
        diffs["lockStatus"] = current.get("lockStatus").get("value")
    # alarm
    if previous.get("alarm").get("value") != current.get("alarm").get("value"):
        diffs["alarm"] = current.get("alarm").get("value")
    # remoteStartStatus
    if previous.get("remoteStartStatus").get("value") != current.get("remoteStartStatus").get("value"):
        diffs["remoteStartStatus"] = current.get("remoteStartStatus").get("value")
    # tirePressure
    if previous.get("tirePressure").get("value") != current.get("tirePressure").get("value"):
        diffs["tirePressure"] = current.get("tirePressure").get("value")
    # TMPS
    adjustKPA = 0.1450377 if _PSI else 1.0
    oldTirePressures = [
        int(round(float(previous.get("TPMS").get("leftFrontTirePressure").get("value")) * adjustKPA, 0)),
        int(round(float(previous.get("TPMS").get("rightFrontTirePressure").get("value")) * adjustKPA, 0)),
        int(round(float(previous.get("TPMS").get("outerLeftRearTirePressure").get("value")) * adjustKPA, 0)),
        int(round(float(previous.get("TPMS").get("outerRightRearTirePressure").get("value")) * adjustKPA, 0)),
    ]
    newTirePressures = [
        int(round(float(current.get("TPMS").get("leftFrontTirePressure").get("value")) * adjustKPA, 0)),
        int(round(float(current.get("TPMS").get("rightFrontTirePressure").get("value")) * adjustKPA, 0)),
        int(round(float(current.get("TPMS").get("outerLeftRearTirePressure").get("value")) * adjustKPA, 0)),
        int(round(float(current.get("TPMS").get("outerRightRearTirePressure").get("value")) * adjustKPA, 0)),
    ]
    for i in range(len(oldTirePressures)):
        if oldTirePressures[i] != newTirePressures[i]:
            diffs["TPMS"] = newTirePressures
            break
    # batteryFillLevel
    if previous.get("batteryFillLevel").get("value") != current.get("batteryFillLevel").get("value"):
        diffs["batteryFillLevel"] = current.get("batteryFillLevel").get("value")
    # elVehDTE
    if round(float(previous.get("elVehDTE").get("value")), 6) != round(float(current.get("elVehDTE").get("value")), 6):
        diffs["elVehDTE"] = round(current.get("elVehDTE").get("value"), 1)
    # chargingStatus
    if previous.get("chargingStatus").get("value") != current.get("chargingStatus").get("value"):
        diffs["chargingStatus"] = current.get("chargingStatus").get("value")
    # plugStatus
    if previous.get("plugStatus").get("value") != current.get("plugStatus").get("value"):
        diffs["plugStatus"] = current.get("plugStatus").get("value")
    # doorStatus
    if previous.get("doorStatus").get("rightRearDoor").get("value") != current.get("doorStatus").get(
        "rightRearDoor"
    ).get("value"):
        diffs["rightRearDoor"] = current.get("doorStatus").get("rightRearDoor").get("value")
    if previous.get("doorStatus").get("leftRearDoor").get("value") != current.get("doorStatus").get("leftRearDoor").get(
        "value"
    ):
        diffs["leftRearDoor"] = current.get("doorStatus").get("leftRearDoor").get("value")
    if previous.get("doorStatus").get("driverDoor").get("value") != current.get("doorStatus").get("driverDoor").get(
        "value"
    ):
        diffs["driverDoor"] = current.get("doorStatus").get("driverDoor").get("value")
    if previous.get("doorStatus").get("passengerDoor").get("value") != current.get("doorStatus").get(
        "passengerDoor"
    ).get("value"):
        diffs["passengerDoor"] = current.get("doorStatus").get("passengerDoor").get("value")
    if previous.get("doorStatus").get("hoodDoor").get("value") != current.get("doorStatus").get("hoodDoor").get(
        "value"
    ):
        diffs["hoodDoor"] = current.get("doorStatus").get("hoodDoor").get("value")
    if previous.get("doorStatus").get("tailgateDoor").get("value") != current.get("doorStatus").get("tailgateDoor").get(
        "value"
    ):
        diffs["tailgateDoor"] = current.get("doorStatus").get("tailgateDoor").get("value")
    if previous.get("doorStatus").get("innerTailgateDoor").get("value") != current.get("doorStatus").get(
        "innerTailgateDoor"
    ).get("value"):
        diffs["innerTailgateDoor"] = current.get("doorStatus").get("innerTailgateDoor").get("value")

    if len(diffs) > 0:
        _LOGGER.info(f"{diffs}")
        if diffs.get("latitude") or diffs.get("longitude"):
            decode_location(current)

    return diffs


def get_vehicle_status():
    global _VEHICLECLIENT
    status = None
    tries = 3
    while tries > 0:
        try:
            status = _VEHICLECLIENT.status()
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


def process_trip(start, end):
    global _MILES, _EXTENDED
    unit = "km"
    elapsedTime = (last_status_update(end) - last_status_update(start)).total_seconds() / 3600
    percentUsed = float(start.get("batteryFillLevel").get("value")) - float(end.get("batteryFillLevel").get("value"))
    batteryUsed = percentUsed * 0.01
    kwhUsed = batteryUsed * 88.0 if _EXTENDED else 68.0
    distance = end.get("odometer").get("value") - start.get("odometer").get("value")
    distpkwh = 99.9 if kwhUsed <= 0.0 else distance / kwhUsed
    averageSpeed = distance / elapsedTime
    if _MILES:
        distance = distance * 0.6214
        distpkwh = 99.9 if kwhUsed <= 0.0 else distance / kwhUsed
        averageSpeed = distance / elapsedTime
        unit = "miles"
    # ### _LOGGER.info(f"start/end times: {start.get('lastModifiedDate')}/{end.get('lastModifiedDate')}")
    _LOGGER.info(
        f"Trip took {elapsedTime:.2f} hours, over {distance:.2f} {unit} using {kwhUsed:.2f} kWh, {distpkwh:.2f} {unit} per kWh, {averageSpeed:.1f} {unit} per hour"
    )


def main():
    """Set up and start FordPass Connect."""

    global _VEHICLECLIENT, _GEOCLIENT, _ABRPCLIENT

    logfiles.create_application_log(_LOGGER)
    _LOGGER.info(f"Ford Connect test utility {version.get_version()}")

    config = read_config()
    if not config:
        _LOGGER.error("Error processing YAML configuration - exiting")
        return

    _ABRPCLIENT = AbrpClient(config.abrp.api_key, config.abrp.token)
    _GEOCLIENT = GeocodioClient(config.geocodio.api_key)
    _VEHICLECLIENT = Vehicle(
        username=config.fordconnect.vehicle.username,
        password=config.fordconnect.vehicle.password,
        vin=config.fordconnect.vehicle.vin,
    )
    currentStatus = get_vehicle_status()
    _ABRPCLIENT.post(currentStatus)

    decode_lastupdate(status=currentStatus)
    decode_ignition(status=currentStatus)
    decode_plug(status=currentStatus)
    decode_charging(status=currentStatus)
    decode_preconditioning(status=currentStatus)
    decode_odometer(status=currentStatus)
    decode_dte(status=currentStatus)
    decode_soc(status=currentStatus)
    decode_tpms(status=currentStatus)
    decode_doors(status=currentStatus)
    decode_locked(status=currentStatus)
    decode_windows(status=currentStatus)
    decode_alarm(status=currentStatus)
    decode_location(status=currentStatus)

    tripStarted = None
    tripEnded = None
    previousStatus = currentStatus
    try:
        limit = 4000
        passes = 0
        while True:
            time.sleep(30)

            passes += 1
            if passes > limit:
                break

            try:
                currentStatus = get_vehicle_status()
            except requests.ConnectionError:
                continue

            previousModified = last_status_update(previousStatus)
            currentModified = last_status_update(currentStatus)
            if currentModified > previousModified:
                _ABRPCLIENT.post(currentStatus)
                diffs = differences(previous=previousStatus, current=currentStatus)

                if not tripStarted and diffs.get("ignitionStatus") and diffs.get("ignitionStatus") == "Run":
                    tripStarted = currentStatus
                elif not tripStarted and diffs.get("ignitionStatus") and diffs.get("ignitionStatus") == "Start":
                    tripStarted = currentStatus
                elif diffs.get("ignitionStatus") and diffs.get("ignitionStatus") == "Off":
                    tripEnded = currentStatus
                if tripStarted and tripEnded:
                    process_trip(start=tripStarted, end=tripEnded)
                    tripStarted = None
                    tripEnded = None

                previousStatus = currentStatus

    except Exception as e:
        _LOGGER.error(f"Unexpected exception: {e}")


if __name__ == "__main__":
    # make sure we can run this
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 8:
        main()
    else:
        print("python 3.8 or better required")
