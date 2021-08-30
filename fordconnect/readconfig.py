"""Custom YAML file loader with !secrets support."""

import logging
import os
import sys

from dateutil.parser import parse
from pathlib import Path

from collections import OrderedDict
from typing import Dict, List, TextIO, TypeVar, Union

import yaml
from config import config_from_yaml


CONFIG_YAML = "fordconnect.yaml"
SECRET_YAML = "secrets.yaml"

JSON_TYPE = Union[List, Dict, str]  # pylint: disable=invalid-name
DICT_T = TypeVar("DICT_T", bound=Dict)  # pylint: disable=invalid-name

_LOGGER = logging.getLogger()
__SECRET_CACHE: Dict[str, JSON_TYPE] = {}


class ConfigError(Exception):
    """General YAML configurtion file exception."""


class FullLineLoader(yaml.FullLoader):
    """Loader class that keeps track of line numbers."""

    def compose_node(self, parent: yaml.nodes.Node, index: int) -> yaml.nodes.Node:
        """Annotate a node with the first line it was seen."""
        last_line: int = self.line
        node: yaml.nodes.Node = super().compose_node(parent, index)
        node.__line__ = last_line + 1  # type: ignore
        return node


def load_yaml(fname: str) -> JSON_TYPE:
    """Load a YAML file."""
    try:
        with open(fname, encoding="utf-8") as conf_file:
            return parse_yaml(conf_file)
    except UnicodeDecodeError as exc:
        _LOGGER.error("Unable to read file %s: %s", fname, exc)
        raise ConfigError(exc) from exc


def parse_yaml(content: Union[str, TextIO]) -> JSON_TYPE:
    """Load a YAML file."""
    try:
        # If configuration file is empty YAML returns None
        # We convert that to an empty dict
        return yaml.load(content, Loader=FullLineLoader) or OrderedDict()
    except yaml.YAMLError as exc:
        _LOGGER.error(str(exc))
        raise ConfigError(exc) from exc


def _load_secret_yaml(secret_path: str) -> JSON_TYPE:
    """Load the secrets yaml from path."""
    secret_path = os.path.join(secret_path, SECRET_YAML)
    if secret_path in __SECRET_CACHE:
        return __SECRET_CACHE[secret_path]

    _LOGGER.debug("Loading %s", secret_path)
    try:
        secrets = load_yaml(secret_path)
        if not isinstance(secrets, dict):
            raise ConfigError("Secrets is not a dictionary")

    except FileNotFoundError:
        secrets = {}

    __SECRET_CACHE[secret_path] = secrets
    return secrets


def secret_yaml(loader: FullLineLoader, node: yaml.nodes.Node) -> JSON_TYPE:
    """Load secrets and embed it into the configuration YAML."""
    if os.path.basename(loader.name) == SECRET_YAML:
        _LOGGER.error("secrets.yaml: attempt to load secret from within secrets file")
        raise ConfigError("secrets.yaml: attempt to load secret from within secrets file")

    secret_path = os.path.dirname(loader.name)
    home_path = str(Path.home())
    do_walk = os.path.commonpath([secret_path, home_path]) == home_path

    while True:
        secrets = _load_secret_yaml(secret_path)
        if node.value in secrets:
            _LOGGER.debug(
                "Secret %s retrieved from secrets.yaml in folder %s",
                node.value,
                secret_path,
            )
            return secrets[node.value]

        if not do_walk or (secret_path == home_path):
            break
        secret_path = os.path.dirname(secret_path)

    raise ConfigError(f"Secret '{node.value}' not defined")


# fc_vehicle_name
# fc_vehicle_vin
# fc_vehicle_username
# fc_vehicle_password


def check_fordconnect(config):
    options = {}
    fordconnect_key = config.fordconnect
    if not fordconnect_key or "vehicle" not in fordconnect_key.keys():
        _LOGGER.warning("Expected option 'vehicle' in the 'fordconnect' settings")
        return None

    vehicle_key = fordconnect_key.vehicle
    vehicle_keys = ["name", "vin", "username", "password"]
    for key in vehicle_keys:
        if key not in vehicle_key.keys():
            _LOGGER.error(f"Missing required '{key}' option in 'vehicle' settings")
            return None

    options["name"] = vehicle_key.name
    options["vin"] = vehicle_key.vin
    options["username"] = vehicle_key.username
    options["password"] = vehicle_key.password
    return options


def read_config():
    try:
        yaml.FullLoader.add_constructor("!secret", secret_yaml)
        yaml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_YAML)
        config = config_from_yaml(data=yaml_file, read_from_file=True)

        fordconnect_options = check_fordconnect(config)
        if None in [fordconnect_options]:
            return None
        return config

    except Exception as e:
        print(e)
        return None


if __name__ == "__main__":
    # make sure we can run
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 8:
        config = read_config()
    else:
        print("python 3.8 or better required")
