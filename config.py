"""
Configuration file functions and constants for Chlorine
"""

from pathlib import Path
import json
import log

DEFAULT_CONFIG = {
    "token": None,
    "servers": [
        "wss://chats.mistium.com",
        "wss://originchats.0stormy.xyz"
    ],
    "selected_server": 0
}
CONFIG_PATH = "config.json"

def get_value(config_path: str, key: str) -> str | list | int | None:
    """
    Get value via key from JSON config file
    
    :param config_path: Path to config
    :type config_path: str
    :param key: Key to get value from
    :type key: str
    :return: If key exists, returns key value, otherwise returns False
    :rtype: str | bool
    """
    with open(config_path, "r", encoding="utf-8") as f:
        raw_json = f.read()
    json_data = json.loads(raw_json)
    try:
        return json_data[key]
    except KeyError:
        return None

def set_value(config_path: str, key: str, value: str) -> None:
    """
    Set or update value via key from JSON config file
    
    :param config_path: Path to config
    :type config_path: str
    :param key: Key to set
    :type key: str
    :param value: Value to set
    :type value: str
    """
    # Load existing data
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
    except FileNotFoundError:
        json_data = {}

    # Update or add key
    json_data[key] = value

    # Save updated data
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=4, ensure_ascii=False)

def is_config(paths: str | list[str] | tuple[str, ...]) -> bool:
    """
    Checks if any config file existts from one or more configs
    
    :param paths: Path(s) to JSON config file(s)
    :type paths: str | list[str] | tuple[str, ...]
    :return: Config file exists if True, False if not
    :rtype: bool
    """
    path_list: tuple[str, ...]
    
    match paths:
        case str():
            path_list = (paths,)
        case list():
            path_list = tuple(paths)
        case tuple():
            path_list = paths
        case _:
            raise TypeError("Expected str or tuple")

    for path in path_list:
        if Path(path).is_file():
            return True

    return False

def create_config(config_path: str) -> bool:
    """
    Creates a config at a given file path if one doesn't exist already
    
    :param path: Path to JSON config
    :type config_path: str
    :return: Returns true if file was made and False if it already exits
    :rtype: bool
    """
    # Check if a config file exist already
    if is_config(config_path):
        log.info("Config file already exists")
        return False
    else:
        # Convert default config object to a JSON string
        converted_config = json.dumps(DEFAULT_CONFIG, indent=4)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(converted_config)
        return True