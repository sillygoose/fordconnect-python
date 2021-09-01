"""ABRP Telemetry API integration"""

import logging
import time
import requests
import urllib
import json


_LOGGER = logging.getLogger("fordconnect")


class AbrpClient:
    """Class to encapsulate the ABRP Telemetry API."""

    def __init__(self, api_key, token):
        """Create the ABRP Telemetry client."""
        self._api_key = api_key
        self._token = token
        self._last_data_time = None

    def post(self, status):
        """Post an update to the ABRP Telemetry client."""

        utc = int(time.time())
        soc = float(status.get("batteryFillLevel").get("value"))
        latitude = status.get("gps").get("latitude")
        longitude = status.get("gps").get("longitude")
        odometer = float(status.get("odometer").get("value"))
        chargingStatus = status.get("chargingStatus").get("value")
        ignitionStatus = 1 if status.get("ignitionStatus").get("value") == "Off" else 0
        data = {
            "utc": utc,
            "soc": soc,
            "odometer": odometer,
            "lat": latitude,
            "lon": longitude,
            "is_parked": ignitionStatus,
            "is_charging": chargingStatus,
        }
        params = {"token": self._token, "api_key": self._api_key, "tlm": json.dumps(data, separators=(",", ":"))}
        url = "https://api.iternio.com/1/tlm/send?" + urllib.parse.urlencode(params)
        try:
            status = requests.get(url)
            if status.status_code == 200:
                self._last_data_time = int(time.time())
        except:
            status = None

        if status.status_code == 200:
            # _LOGGER.info(f"ABRP telemetry update was successful")
            pass
        else:
            _LOGGER.info(f"ABRP telemetry update failed: {status.status_code}")
