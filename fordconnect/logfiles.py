"""Module handling the application and production log files."""

import os
import sys
import logging
from datetime import datetime


_LOG_FILE = "log/fordconnect"
_LOG_FORMAT = "[%(asctime)s] [%(module)s] [%(levelname)s] %(message)s"


def create_application_log(app_logger):
    """Create the application log."""
    now = datetime.now()
    filename = os.path.expanduser(_LOG_FILE + "_" + now.strftime("%Y-%m-%d") + ".log")

    # Create the directory if needed
    filename_parts = os.path.split(filename)
    if filename_parts[0] and not os.path.isdir(filename_parts[0]):
        os.mkdir(filename_parts[0])
    filename = os.path.abspath(filename)
    logging.basicConfig(
        filename=filename,
        filemode="w+",
        format=_LOG_FORMAT,
        level=logging.INFO,
    )

    # Add some console output for anyone watching
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    app_logger.addHandler(console_handler)
    # ### app_logger.setLevel(logging.INFO)

    # First entry
    app_logger.info("Created application log %s", filename)
