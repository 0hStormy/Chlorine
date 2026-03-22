"""
Handles configuration file for Chlorine.
Made with <3 by Stormy
"""

import json
from pathlib import Path
import platformdirs


DEFAULT_CONFIG = {
    "token": "",
    "theme": "System",
    "servers": ["wss://chats.mistium.com"],
}


def get_config_path() -> str:
    """
    Returns a path to the program's config folder

    :return: Path to config folder
    :rtype: str
    """
    return platformdirs.user_config_dir("Chlorine", "xhlowi")


def create_config() -> bool:
    """
    Tries to create a config file if it doesn't already exist.

    :return: True if config was created, False if it exists already
    :rtype: bool
    """

    # Checks if config already exists
    config_path = Path(get_config_path()) / "chlorine.json"
    if config_path.exists():
        return False

    # Creates needed directories and write config file to disk
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=4)

    return True


def read_from_config(key: str):
    """
    Read value from key in config, could return any value.

    :param key: Key to read
    :type key: str
    """
    # Get config file
    config_path = Path(get_config_path()) / "chlorine.json"
    with config_path.open("r") as f:
        config = json.loads(f.read())
    return config[key]


def write_to_config(key: str, value) -> None:
    """
    Write/modify key-value pair to config

    :param key: Key to modify
    :type key: str
    :param value: Value to assign key
    """
    # Get config file
    config_path = Path(get_config_path()) / "chlorine.json"
    with config_path.open("r") as f:
        config = json.loads(f.read())

    # Modify key-value pair and write file
    config[key] = value
    with config_path.open("w") as f:
        json.dump(config, f, indent=4)
