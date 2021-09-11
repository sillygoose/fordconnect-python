"""Code to interface with the FordPass Connect API as used in the FordPass app"""

import logging
import sys
import time
from datetime import datetime
import requests
import json
import pprint

import version
import logfiles
from readconfig import read_config
from utilities import fordtime_to_datetime

from fordpass import Vehicle
from geocodio import GeocodioClient
from abrp import AbrpClient
from usgs_elevation import usgs_alt


_VEHICLECLIENT = None
_GEOCLIENT = None
_ABRPCLIENT = None

_METRIC = False
_EXTENDED = True
_PSI = True
_LOGSTATUS = True

_LOGGER = logging.getLogger("fordconnect")

_UNITS = [
    {"speed": "mph", "distance": "miles", "elevation": "ft"},
    {"speed": "kph", "distance": "km", "elevation": "m"},
]

# journeys use meters per second, meters, and meters, adjust accordingly when other units are used
_CONVERSIONS = [
    {"speed": 3.6 * 0.6214, "distance": 0.001 * 0.6214, "elevation": 3.2808},
    {"speed": 3.6, "distance": 0.001, "elevation": 1.0},
]

# standard and extended battery sizes in kWh
_BATTERY = [68, 88]


def last_status_update(status, useUTC=True):
    return fordtime_to_datetime(status.get("lastModifiedDate"), useUTC)


def server_time(status, useUTC=True):
    return fordtime_to_datetime(status.get("serverTime"), useUTC)


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
    _LOGGER.info(
        f"Last modified {last_status_update(status, useUTC=False).strftime('%Y-%m-%d %H:%M')}, time since last update {time_since_update(status)}"
    )


# 'Off', 'Start', 'Run'
def decode_ignition(status):
    ignitionStatus = status.get("ignitionStatus").get("value")
    _LOGGER.info(f"Ignition is '{ignitionStatus}'")


# 'NotReady', 'ChargingAC', 'ChargeTargetReached', 'ChargeStartCommanded', 'ChargeStopCommanded'
def decode_charging(status):
    chargingStatus = status.get("chargingStatus").get("value")
    _LOGGER.info(f"Charging status is '{chargingStatus}'")


# 0 - Not plugged in, 1 - Plugged in
def decode_plug(status):
    plugStatus = status.get("plugStatus").get("value")
    plugState = "plugged in" if plugStatus else "not plugged in"
    _LOGGER.info(f"Vehicle is {plugState}")


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
    global _METRIC

    odometer_m = float(status.get("odometer").get("value")) * 1000
    odometer_km = odometer_m * _CONVERSIONS[_METRIC == True].get("distance")
    odometer_miles = odometer_m * _CONVERSIONS[_METRIC == False].get("distance")
    if _METRIC:
        _LOGGER.info(f"Odometer reads {odometer_km:.1f} {_UNITS[_METRIC==True].get('distance')}")
    else:
        _LOGGER.info(
            f"Odometer reads {odometer_km:.1f} {_UNITS[_METRIC==True].get('distance')} ({odometer_miles:.1f} {_UNITS[_METRIC==False].get('distance')})"
        )


def decode_dte(status):
    global _METRIC

    dte_m = float(status.get("elVehDTE").get("value")) * 1000
    dte_km = dte_m * _CONVERSIONS[_METRIC == True].get("distance")
    dte_miles = dte_m * _CONVERSIONS[_METRIC == False].get("distance")
    if _METRIC:
        _LOGGER.info(f"Estimated range is {dte_km:.1f} {_UNITS[_METRIC==True].get('distance')}")
    else:
        _LOGGER.info(
            f"Estimated range is {dte_km:.1f} {_UNITS[_METRIC==True].get('distance')} ({dte_miles:.1f} {_UNITS[_METRIC==False].get('distance')})"
        )


def decode_soc(status):
    soc = float(status.get("batteryFillLevel").get("value"))
    battery = status.get("battery")
    _LOGGER.info(
        f"Battery is at {soc:.1f}% of capacity, health is '{battery.get('batteryHealth').get('value')}', status is {battery.get('batteryStatusActual').get('value')}"
    )


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


def decode_location(status) -> str:
    global _GEOCLIENT
    locationInfo = _GEOCLIENT.reverse((status.get("gps").get("latitude"), status.get("gps").get("longitude")))
    addr_components = locationInfo["results"][0]["address_components"]
    _LOGGER.debug(
        f"Vehicle location is near '{addr_components.get('formatted_street', '???')}, {addr_components.get('city', '')}'"
    )
    return f"{addr_components.get('formatted_street', '???')}, {addr_components.get('city', '')}"


def differences(previous, current):
    global _PSI, _LOGSTATUS

    diffs = {}

    # ignitionStatus
    if previous.get("ignitionStatus").get("value") != current.get("ignitionStatus").get("value"):
        diffs["ignitionStatus"] = current.get("ignitionStatus").get("value")
    # odometer
    if previous.get("odometer").get("value") != current.get("odometer").get("value"):
        diffs["odometer"] = current.get("odometer").get("value")
    # elVehDTE
    if round(float(previous.get("elVehDTE").get("value")), 6) != round(float(current.get("elVehDTE").get("value")), 6):
        diffs["elVehDTE"] = round(current.get("elVehDTE").get("value"), 1)
    # batteryFillLevel
    if previous.get("batteryFillLevel").get("value") != current.get("batteryFillLevel").get("value"):
        diffs["batteryFillLevel"] = current.get("batteryFillLevel").get("value")
    # battery
    if previous.get("battery").get("batteryHealth").get("value") != current.get("battery").get("batteryHealth").get(
        "value"
    ):
        diffs["batteryHealth"] = current.get("battery").get("batteryHealth").get("value")
    if previous.get("battery").get("batteryStatusActual").get("value") != current.get("battery").get(
        "batteryStatusActual"
    ).get("value"):
        diffs["batteryStatusActual"] = current.get("battery").get("batteryStatusActual").get("value")
    # batteryPerfStatus
    if previous.get("batteryPerfStatus").get("value") != current.get("batteryPerfStatus").get("value"):
        diffs["batteryPerfStatus"] = current.get("batteryPerfStatus").get("value")
    # batteryChargeStatus
    if previous.get("batteryChargeStatus").get("value") != current.get("batteryChargeStatus").get("value"):
        diffs["batteryChargeStatus"] = current.get("batteryChargeStatus").get("value")
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
    # chargingStatus
    if previous.get("chargingStatus").get("value") != current.get("chargingStatus").get("value"):
        diffs["chargingStatus"] = current.get("chargingStatus").get("value")
    # chargeStartTime
    if previous.get("chargeStartTime").get("value") != current.get("chargeStartTime").get("value"):
        diffs["chargeStartTime"] = current.get("chargeStartTime").get("value")
    # chargeEndTime
    if previous.get("chargeEndTime").get("value") != current.get("chargeEndTime").get("value"):
        diffs["chargeEndTime"] = current.get("chargeEndTime").get("value")
    # plugStatus
    if previous.get("plugStatus").get("value") != current.get("plugStatus").get("value"):
        diffs["plugStatus"] = current.get("plugStatus").get("value")
    # log modified times
    # diffs["lastModifiedDate"] = previous.get("lastModifiedDate") + "/" + current.get("lastModifiedDate")
    # log server times
    # diffs["serverTime"] = previous.get("serverTime") + "/" + current.get("serverTime")
    # firmwareUpgInProgress
    if previous.get("firmwareUpgInProgress").get("value") != current.get("firmwareUpgInProgress").get("value"):
        diffs["firmwareUpgInProgress"] = current.get("firmwareUpgInProgress").get("value")
    # deepSleepInProgress
    if previous.get("deepSleepInProgress").get("value") != current.get("deepSleepInProgress").get("value"):
        diffs["deepSleepInProgress"] = current.get("deepSleepInProgress").get("value")
    # PrmtAlarmEvent
    if previous.get("PrmtAlarmEvent").get("value") != current.get("PrmtAlarmEvent").get("value"):
        diffs["PrmtAlarmEvent"] = current.get("PrmtAlarmEvent").get("value")
    # remoteStartStatus
    if previous.get("remoteStartStatus").get("value") != current.get("remoteStartStatus").get("value"):
        diffs["remoteStartStatus"] = current.get("remoteStartStatus").get("value")
    # preCondStatusDsply
    if previous.get("preCondStatusDsply").get("value") != current.get("preCondStatusDsply").get("value"):
        diffs["preCondStatusDsply"] = current.get("preCondStatusDsply").get("value")
    # tirePressure
    if previous.get("tirePressure").get("value") != current.get("tirePressure").get("value"):
        diffs["tirePressure"] = current.get("tirePressure").get("value")
    # oilLife
    if previous.get("oil").get("oilLife") != current.get("oil").get("oilLife"):
        diffs["oilLife"] = current.get("oil").get("oilLife")
    # oilLifeActual
    if previous.get("oil").get("oilLifeActual") != current.get("oil").get("oilLifeActual"):
        diffs["oilLifeActual"] = current.get("oil").get("oilLifeActual")
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
    # fstChrgBulkTEst
    if previous.get("dcFastChargeData").get("fstChrgBulkTEst").get("value") != current.get("dcFastChargeData").get(
        "fstChrgBulkTEst"
    ).get("value"):
        diffs["fstChrgBulkTEst"] = current.get("dcFastChargeData").get("fstChrgBulkTEst").get("value")
    # fstChrgCmpltTEst
    if previous.get("dcFastChargeData").get("fstChrgCmpltTEst").get("value") != current.get("dcFastChargeData").get(
        "fstChrgCmpltTEst"
    ).get("value"):
        diffs["fstChrgCmpltTEst"] = current.get("dcFastChargeData").get("fstChrgCmpltTEst").get("value")
    # batteryTracLowChargeThreshold
    if previous.get("batteryTracLowChargeThreshold").get("value") != current.get("batteryTracLowChargeThreshold").get(
        "value"
    ):
        diffs["batteryTracLowChargeThreshold"] = current.get("batteryTracLowChargeThreshold").get("value")
    # battTracLoSocDDsply
    if previous.get("battTracLoSocDDsply").get("value") != current.get("battTracLoSocDDsply").get("value"):
        diffs["battTracLoSocDDsply"] = current.get("battTracLoSocDDsply").get("value")
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
        # if diffs.get("latitude") or diffs.get("longitude"):
        #    decode_location(current)
    else:
        if _LOGSTATUS:
            log_differences(previous, current)

    return diffs


def log_differences(previous, current):
    previousJSON = json.dumps(previous)
    currentJSON = json.dumps(current)
    with open("log/previous.txt", "w") as previousFile:
        prev = pprint.PrettyPrinter(indent=0, width=10, sort_dicts=True, stream=previousFile)
        prev.pprint(previousJSON)
    with open("log/current.txt", "w") as currentFile:
        cur = pprint.PrettyPrinter(indent=0, width=10, sort_dicts=True, stream=currentFile)
        cur.pprint(currentJSON)


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


def process_trip(start, end) -> None:
    """Process the starting and ending status reports for a trip."""

    global _METRIC, _EXTENDED, _CONVERSIONS, _UNITS, _BATTERY

    elapsedTimeHours = (last_status_update(end) - last_status_update(start)).total_seconds() / 3600

    percentUsed = float(start.get("batteryFillLevel").get("value")) - float(end.get("batteryFillLevel").get("value"))
    kwhUsed = percentUsed * 0.01 * _BATTERY[_EXTENDED]

    # Must be meters for conversion lookup table
    dist_km = end.get("odometer").get("value") - start.get("odometer").get("value")
    dist_m = dist_km * 1000
    distance = dist_m * _CONVERSIONS[_METRIC].get("distance")

    distpkwh = 99.999 if kwhUsed <= 0.0 else distance / kwhUsed
    averageSpeed = distance / elapsedTimeHours

    startingElevation = usgs_alt(lat=start.get("gps").get("latitude"), lon=start.get("gps").get("longitude"))
    endingElevation = usgs_alt(lat=end.get("gps").get("latitude"), lon=end.get("gps").get("longitude"))
    deltaElevation = (endingElevation - startingElevation) * _CONVERSIONS[_METRIC].get("elevation")

    _LOGGER.info(
        f"Trip took {elapsedTimeHours:.2f} hours, {distance:.2f} {_UNITS[_METRIC].get('distance')} using {kwhUsed:.2f} kWh, "
        f"{distpkwh:.2f} {_UNITS[_METRIC].get('distance')} per kWh, average speed was {averageSpeed:.1f} {_UNITS[_METRIC].get('speed')}, "
        f"elevation change of {deltaElevation:.0f} {_UNITS[_METRIC].get('elevation')}"
    )
    _LOGGER.info(f"")


def main() -> None:
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
    decode_odometer(status=currentStatus)
    decode_dte(status=currentStatus)
    decode_soc(status=currentStatus)
    decode_tpms(status=currentStatus)
    decode_ignition(status=currentStatus)
    decode_plug(status=currentStatus)
    decode_charging(status=currentStatus)
    decode_preconditioning(status=currentStatus)
    decode_doors(status=currentStatus)
    decode_locked(status=currentStatus)
    decode_windows(status=currentStatus)
    decode_alarm(status=currentStatus)
    decode_location(status=currentStatus)
    _LOGGER.info(f"Current location '{decode_location(status=currentStatus)}'")

    tripStarted = None
    tripEnded = None
    previousStatus = currentStatus
    try:
        limit = 4000
        passes = 0
        while True:
            time.sleep(15)

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

                ignitionStartStates = ["Start", "Run"]
                ignitionStopStates = ["Off"]
                if not tripStarted:
                    if diffs.get("ignitionStatus") in ignitionStartStates:
                        tripStarted = currentStatus
                        _LOGGER.info(f"")
                        _LOGGER.info(f"New trip, departing '{decode_location(status=currentStatus)}'")
                elif diffs.get("ignitionStatus") in ignitionStopStates:
                    tripEnded = currentStatus

                if tripStarted and tripEnded:
                    _LOGGER.info(f"Trip ended, arrived at '{decode_location(status=currentStatus)}'")
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
