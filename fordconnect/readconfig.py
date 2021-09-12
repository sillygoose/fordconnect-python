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
__SECRET_CACHE: Dict[str, JSON_TYPE] = {}
_LOGGER = logging.getLogger("fordconnect")


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

    logging.debug("Loading %s", secret_path)
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


def check_fordconnect(config):
    """Check for Ford Connect options"""
    try:
        vehicleOptions = config.fordconnect.as_dict()
    except:
        return {}

    options = {}
    vehicle_keys = ['name', 'vin', 'username', 'password']
    for key in vehicle_keys:
        if key not in vehicleOptions.keys():
            _LOGGER.error(f"Missing required '{key}' option in 'fordconnect' settings")
            return {}
        options[key] = vehicleOptions.get(key, None)
    return options


def check_geocodio(config):
    """Check for geocodio options and return"""
    try:
        geocodioOptions = config.geocodio.as_dict()
    except:
        return {}

    options = {}
    geocodio_keys = ['enable', 'api_key']
    for key in geocodio_keys:
        if key not in geocodioOptions.keys():
            _LOGGER.error(f"Missing required '{key}' option in 'geocodio' settings")
            return {}
        options[key] = geocodioOptions.get(key, None)
    return options


def check_abrp(config):
    """Check for geocodio options and return"""
    try:
        abrpOptions = config.abrp.as_dict()
    except:
        return {}

    options = {}
    abrp_keys = ["enable", "api_key", "token"]
    for key in abrp_keys:
        if key not in abrpOptions.keys():
            _LOGGER.error(f"Missing required '{key}' option in 'abrp' settings")
            return {}
        options[key] = abrpOptions.get(key, None)
    return options


def read_config():
    try:
        yaml.FullLoader.add_constructor("!secret", secret_yaml)
        yaml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_YAML)
        config = config_from_yaml(data=yaml_file, read_from_file=True)

        options = {}
        options['fordconnect'] = check_fordconnect(config)
        options['geocodio'] = check_geocodio(config)
        options['abrp'] = check_abrp(config)
        return options

    except Exception as e:
        print(e)
        return None


if __name__ == "__main__":
    # make sure we can run
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 9:
        config = read_config()
    else:
        print("python 3.9 or newer required")
