# fordconnect
Application to play around with the FordPass Connect API. Besides display the vehicle state, an option to send the SOC to ABRP is available.

## Installation
Python 3.8 or better is required, you can then install the Python requirements for this application:
```
    git clone https://github.com/sillygoose/fordconnect
    cd fordconnect
    pip3 install -e .
```

## Use
The `fordconnect.yaml` file is read to learn the VIN, username, and password needed by the FordPass Connect API to access the vehicle status.  In order to avoid accidental publication of the private data, a `secrets.yaml` file is used to supply these from outside the repo code.

Rename the `sample_secrets.yaml` file to `secrets.yaml` and edit to match your Ford COnnect VIN and login (if you don't wish to use secrets then edit `fordconnect.yaml` to remove the `!secret` references).  The `secrets.yaml` file is tagged in the `.gitignore` file and will not be included in the repository but if you wish you can put `secrets.yaml` in any parent directory as `fordconnect` will start in the current directory and look in each parent directory up to your home directory for it (or just the current directory if you are not running in a user profile).

Run the application from the command line using Python 3.8 or later:

```
    cd fordconnect
    python3 fordconnect.py
```

## Thanks
Thanks for the following packages used to build this software:
- clarkd/fordpass-python library
    - https://github.com/clarkd/fordpass-python
- ABRP Telemetry API
    - https://documenter.getpostman.com/view/7396339/SWTK5a8w?version=latest
- YAML configuration file support
    - https://python-configuration.readthedocs.io

