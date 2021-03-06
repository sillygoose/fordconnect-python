# fordconnect
Python code to play around with the FordPass Connect API.  Besides display the vehicle state, an option to send the SOC to ABRP is available (requires an API key from ABRP).

The FordPass Connect API is very limited, an update is sent when the car is turned on, then about a minute later, and then when the car is turned off.  You can get more updates when events happen like a TPMS warning.  Updates also occur while charging and there may other events that I have not yet encountered.

Frankly there needs to be a easier, lightweight way for vehicle data to be accessed along with more useful datapoints.


## Installation
Python 3.9 or newer is required, you can then install the Python requirements for this application:
```
    git clone https://github.com/sillygoose/fordconnect-python
    cd fordconnect-python
    pip3 install -e .
```

## Use
The `fordconnect.yaml` file is read to learn the VIN, username, and password needed by the FordPass Connect API to access the vehicle status.  In order to avoid accidental publication of the private data, a `secrets.yaml` file is used to supply these from outside the repo code.

Rename the `sample_secrets.yaml` file to `secrets.yaml` and edit to match your Ford Connect VIN and login (if you don't wish to use secrets then edit `fordconnect.yaml` to remove the `!secret` references).  The `secrets.yaml` file is tagged in the `.gitignore` file and will not be included in the repository but if you wish you can put `secrets.yaml` in any parent directory as `fordconnect` will start in the current directory and look in each parent directory up to your home directory for it (or just the current directory if you are not running in a user profile).

Also included in the `fordconnect.yaml` file are the keys used to access reverse geocoding with Geocodio and sending updates to A Better Route Planner (ABRP).  Leave these disabled until you have API keys that will allow their use.

The following Python modules can be used to request data from the FordPass API:

#### - fordconnect
This runs in a loop looking for status updates.  Crude but good for testing if you triger events with the FordPass app.

#### - chargelogs
#### - journeys
#### - plugstatus
#### - triplogs
These are standlone Python modules that access the API to pull the specfic data for viewing.


## Notes
- Reported distance per kWh results are less accurate for short trips since Ford reports the state of charge (SOC) in 0.5 units and the distance is truncated (see the next note).
- The odometer readings sent from the vehicle are in kilometerS with a tenth digit that is always zero.
- New API calls for plug status, journeys, and charging logs require a modified fordpass-python library.


## Thanks
Thanks for the following packages used to build/develop this software:
- clarkd/fordpass-python library
    - https://github.com/clarkd/fordpass-python
- ABRP Telemetry API
    - https://documenter.getpostman.com/view/7396339/SWTK5a8w?version=latest
- Geocodio
    - https://www.geocod.io
- YAML configuration file support
    - https://python-configuration.readthedocs.io
- mitmproxy
    - https://mitmproxy.org