# coding: utf-8
"""
This module handles the configuration management for Flatisfy.

It loads the default configuration, then overloads it with the provided config
file and then overloads it with command-line options.
"""
from __future__ import absolute_import, print_function, unicode_literals
from builtins import str

import json
import logging
import os
import sys
import traceback

import appdirs

from flatisfy import tools


# Default configuration
DEFAULT_CONFIG = {
    # Constraints to match
    "constraints": {
        "type": None,  # RENT, SALE, SHARING
        "house_types": [],  # List of house types, must be in APART, HOUSE,
                            # PARKING, LAND, OTHER or UNKNOWN
        "postal_codes": [],  # List of postal codes
        "area": (None, None),  # (min, max) in m^2
        "cost": (None, None),  # (min, max) in currency unit
        "rooms": (None, None),  # (min, max)
        "bedrooms": (None, None),  # (min, max)
        "time_to": {}  # Dict mapping names to {"gps": [lat, lng],
                       #                        "time": (min, max) }
                       # Time is in seconds
    },
    # Navitia API key
    "navitia_api_key": None,
    # Number of filtering passes to run
    "passes": 3,
    # Maximum number of entries to fetch
    "max_entries": None,
    # Directory in wich data will be put. ``None`` is XDG default location.
    "data_directory": None,
    # Path to the modules directory containing all Weboob modules. ``None`` if
    # ``weboob_modules`` package is pip-installed, and you want to use
    # ``pkgresource`` to automatically find it.
    "modules_path": None,
    # SQLAlchemy URI to the database to use
    "database": None,
    # Path to the Whoosh search index file. Use ``None`` to put it in
    # ``data_directory``.
    "search_index": None,
    # Web app port
    "port": 8080,
    # Web app host to listen on
    "host": "127.0.0.1",
    # Web server to use to serve the webapp (see Bottle deployment doc)
    "webserver": None,
    # List of Weboob backends to use (default to any backend available)
    "backends": None,
}

LOGGER = logging.getLogger(__name__)


def validate_config(config):
    """
    Check that the config passed as argument is a valid configuration.

    :param config: A config dictionary to fetch.
    :return: ``True`` if the configuration is valid, ``False`` otherwise.
    """
    def _check_constraints_bounds(bounds):
        """
        Check the bounds for numeric constraints.
        """
        assert len(bounds) == 2
        assert all(
            x is None or
            (
                isinstance(x, (float, int)) and
                x >= 0
            )
            for x in bounds
        )
        if bounds[0] is not None and bounds[1] is not None:
            assert bounds[1] > bounds[0]

    try:
        # Note: The traceback fetching code only handle single line asserts.
        # Then, we disable line-too-long pylint check and E501 flake8 checks
        # and use long lines whenever needed, in order to have the full assert
        # message in the log output.
        # pylint: disable=locally-disabled,line-too-long
        assert "type" in config["constraints"]
        assert isinstance(config["constraints"]["type"], (str, unicode))
        assert config["constraints"]["type"].upper() in ["RENT",
                                                         "SALE", "SHARING"]

        assert "house_types" in config["constraints"]
        assert config["constraints"]["house_types"]
        for house_type in config["constraints"]["house_types"]:
            assert house_type.upper() in ["APART", "HOUSE", "PARKING", "LAND",
                                          "OTHER", "UNKNOWN"]

        assert "postal_codes" in config["constraints"]
        assert config["constraints"]["postal_codes"]

        assert "area" in config["constraints"]
        _check_constraints_bounds(config["constraints"]["area"])

        assert "cost" in config["constraints"]
        _check_constraints_bounds(config["constraints"]["cost"])

        assert "rooms" in config["constraints"]
        _check_constraints_bounds(config["constraints"]["rooms"])

        assert "bedrooms" in config["constraints"]
        _check_constraints_bounds(config["constraints"]["bedrooms"])

        assert "time_to" in config["constraints"]
        assert isinstance(config["constraints"]["time_to"], dict)
        for name, item in config["constraints"]["time_to"].items():
            assert isinstance(name, str)
            assert "gps" in item
            assert isinstance(item["gps"], list)
            assert len(item["gps"]) == 2
            assert "time" in item
            _check_constraints_bounds(item["time"])

        assert config["passes"] in [0, 1, 2, 3]
        assert config["max_entries"] is None or (isinstance(config["max_entries"], int) and config["max_entries"] > 0)  # noqa: E501

        assert config["data_directory"] is None or isinstance(config["data_directory"], str)  # noqa: E501
        assert isinstance(config["search_index"], str)
        assert config["modules_path"] is None or isinstance(config["modules_path"], str)  # noqa: E501

        assert config["database"] is None or isinstance(config["database"], str)  # noqa: E501

        assert isinstance(config["port"], int)
        assert isinstance(config["host"], str)
        assert config["webserver"] is None or isinstance(config["webserver"], str)  # noqa: E501
        assert config["backends"] is None or isinstance(config["backends"], list)  # noqa: E501

        return True
    except (AssertionError, KeyError):
        _, _, exc_traceback = sys.exc_info()
        return traceback.extract_tb(exc_traceback)[-1][-1]


def load_config(args=None):
    """
    Load the configuration from file.

    :param args: An argparse args structure.
    :return: The loaded config dict.
    """
    LOGGER.info("Initializing configuration...")
    # Default configuration
    config_data = DEFAULT_CONFIG.copy()

    # Load config from specified JSON
    if args and getattr(args, "config", None):
        LOGGER.debug("Loading configuration from %s.", args.config)
        try:
            with open(args.config, "r") as fh:
                config_data.update(json.load(fh))
        except (IOError, ValueError) as exc:
            LOGGER.error(
                "Unable to load configuration from file, "
                "using default configuration: %s.",
                exc
            )

    # Overload config with arguments
    if args and getattr(args, "passes", None) is not None:
        LOGGER.debug(
            "Overloading number of passes from CLI arguments: %d.",
            args.passes
        )
        config_data["passes"] = args.passes
    if args and getattr(args, "max_entries", None) is not None:
        LOGGER.debug(
            "Overloading maximum number of entries from CLI arguments: %d.",
            args.max_entries
        )
        config_data["max_entries"] = args.max_entries
    if args and getattr(args, "port", None) is not None:
        LOGGER.debug("Overloading web app port: %d.", args.port)
        config_data["port"] = args.port
    if args and getattr(args, "host", None) is not None:
        LOGGER.debug("Overloading web app host: %s.", args.host)
        config_data["host"] = str(args.host)

    # Handle data_directory option
    if args and getattr(args, "data_dir", None) is not None:
        LOGGER.debug("Overloading data directory from CLI arguments.")
        config_data["data_directory"] = args.data_dir
    elif config_data["data_directory"] is None:
        config_data["data_directory"] = appdirs.user_data_dir(
            "flatisfy",
            "flatisfy"
        )
        LOGGER.debug("Using default XDG data directory: %s.",
                     config_data["data_directory"])

    if config_data["database"] is None:
        config_data["database"] = "sqlite:///" + os.path.join(
            config_data["data_directory"],
            "flatisfy.db"
        )

    if config_data["search_index"] is None:
        config_data["search_index"] = os.path.join(
            config_data["data_directory"],
            "search_index"
        )

    config_validation = validate_config(config_data)
    if config_validation is True:
        LOGGER.info("Config has been fully initialized.")
        return config_data
    LOGGER.error("Error in configuration: %s.", config_validation)
    return None


def init_config(output=None):
    """
    Initialize an empty configuration file.

    :param output: File to output content to. Defaults to ``stdin``.
    """
    config_data = DEFAULT_CONFIG.copy()

    if output and output != "-":
        with open(output, "w") as fh:
            fh.write(tools.pretty_json(config_data))
    else:
        print(tools.pretty_json(config_data))
