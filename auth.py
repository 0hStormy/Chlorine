import requests
import webbrowser
import time
import config


def open_linking_page():
    """Opens link to Rotur account link page"""
    webbrowser.open("https://rotur.dev/link")


def generate_auth_code() -> str:
    """
    Gets new Rotur linking code from Rotur API

    :return: Rotur linking code
    :rtype: str
    """
    response = requests.get("https://api.rotur.dev/link/code")
    response_json = response.json()
    return response_json["code"]


def token_from_link(code: str) -> None:
    """
    Waits for user to link account, then gets user token

    :param code: Rotur linking code
    :type code: str
    """
    while True:
        url = f"https://api.rotur.dev/link/user?code={code}"
        response = requests.get(url)

        # Linking incomplete
        if response.status_code == 404:
            time.sleep(2)
            continue

        response_json = response.json()

        # Linking complete
        config.set_value(config.CONFIG_PATH, "token", response_json["token"])
        break
