"""
Rotur account authentication/linking is handled in this script.
Made with <3 by Stormy
"""

import requests
from enum import Enum
import config


class LinkedStatus(Enum):
    LINKED = True
    UNLINKED = False


def get_linking_code() -> str:
    """
    Fetches linking code from Rotur

    :return: Linking code
    :rtype: str
    """
    code_url = "https://api.rotur.dev/link/code"
    response = requests.get(code_url)
    code = response.json()["code"]
    return code


def try_get_token(code: str) -> tuple[LinkedStatus, str]:
    """
    Attempt to get token based on Rotur linking code

    :param code: Linking code
    :type code: str
    :return: Tuple of the linked status and user token
    :rtype: tuple[LinkedStatus, str]
    """
    linking_url = f"https://api.rotur.dev/link/user?code={code}"
    response = requests.get(linking_url)
    is_linked = response.json()["linked"]

    # Return values
    if is_linked:
        link_status = LinkedStatus.LINKED
        token = response.json()["token"]
    else:
        link_status = LinkedStatus.UNLINKED
        token = ""
    return (link_status, token)


def is_authenticated() -> bool:
    """
    Checks if user is authenticated with Rotur based on token in config file.
    
    :return: If user is authenticated
    :rtype: bool
    """
    token = config.read_from_config("token")
    return True if token != "" else False