"""Helper code"""

import logging
from datetime import datetime
from dateutil import tz


_LOGGER = logging.getLogger("fordconnect")


def fordtime_to_datetime(fordTimeString, useUTC=True):
    """Convert Ford UTC time string to local datetime object"""
    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()
    try:
        utc_dt = datetime.strptime(fordTimeString, "%m-%d-%Y %H:%M:%S.%f")
    except:
        utc_dt = datetime.strptime(fordTimeString, "%m-%d-%Y %H:%M:%S")
    utc = utc_dt.replace(tzinfo=from_zone)
    if useUTC:
        return utc
    return utc.astimezone(to_zone)
