"""
Websocket handler for Chlorine.
"""

import requests
import websockets
import asyncio
import json
import config


class Server:
    def __init__(self, url: str, on_event=None) -> None:
        """
        originChats server instance

        :param url: URL to websocket server
        """
        self.loop: asyncio.AbstractEventLoop | None = None
        self.url = url
        self.on_event = on_event
        self.websocket: websockets.ClientConnection | None = None
        self.handshake_data = {}
        self.data = {}
        self.user = {}
        self.validator = ""
        self.channel = "general"

    @staticmethod
    def generate_validator(validator_key: str, token: str) -> str:
        """
        Generates a originChats validator token

        :param validator_key: Unique handshake key
        :type validator_key: str
        :param token: User token
        :type token: str
        :return: Validation token
        :rtype: str
        """
        url = (
            "https://social.rotur.dev/generate_validator"
            f"?key={validator_key}&auth={token}"
        )
        response = requests.get(url)
        if not response.ok:
            return ""
        return response.json()["validator"]

    async def listen(self):
        """
        Start websocket connect with an originChats server
        """
        loop = asyncio.get_running_loop()
        self.loop = loop

        async with websockets.connect(self.url) as websocket:
            self.websocket = websocket
            commands = {
                "handshake": self.handshake,
                "auth_success": self.auth_success,
                "ready": self.ready,
                "ping": self.ping,
                "pong": self.pong,
                "channels_get": self.channels_get,
                "messages_get": self.messages_get,
                "message_new": self.message_new
            }
            while True:
                raw = await self.websocket.recv()
                data = json.loads(raw)
                self.data = data
                cmd = data.get("cmd")
                handler = commands.get(cmd)
                if handler:
                    await handler()
                else:
                    print(f"Unhandled cmd: {cmd}", data)

    async def send_message(self, content):
        """
        Send a user message to server via message_new cmd
        """
        assert self.websocket is not None
        payload = {
            "cmd": "message_new",
            "channel": self.channel,
            "content": content
        }
        await self.websocket.send(json.dumps(payload))

    async def handshake(self):
        """
        Handle handshake and authentication with server
        """
        assert self.websocket is not None

        # Keep handshake data for later
        self.handshake_data = self.data

        # Extract data
        token = config.read_from_config("token")
        validator_key = self.data["val"]["validator_key"]

        # Generate validator
        validator_token = self.generate_validator(validator_key, token)

        # Send message
        payload = {
            "cmd": "auth",
            "validator": validator_token,
        }
        await self.websocket.send(json.dumps(payload))

    async def auth_success(self):
        """
        Handle successful authentication with server
        """
        assert self.websocket is not None
        print("Authentication successfully completed!")

    async def ready(self):
        """
        Handles server-client being ready
        """
        assert self.websocket is not None

        # Saves user state
        self.user = self.data["user"]
        self.validator = self.data["validator"]

        # Confirm readiness to user
        print(f"Logged in as {self.user["nickname"]} ({self.user["username"]})")

        if self.on_event:
            self.on_event("ready", self.handshake_data)

        # Get channels
        payload = {"cmd": "channels_get"}
        await self.websocket.send(json.dumps(payload))

        # Get messages
        payload = {"cmd": "messages_get", "channel": self.channel}
        await self.websocket.send(json.dumps(payload))

    async def ping(self):
        """
        Handles ping server back
        """
        assert self.websocket is not None
        payload = {"cmd": "ping", "val": "pong"}
        await self.websocket.send(json.dumps(payload))

    async def pong(self):
        """
        Handles server pong back
        """
        assert self.websocket is not None

    async def channels_get(self):
        """
        Handles getting channels from server and adding them to UI
        """
        assert self.websocket is not None
        channels = self.data["val"]

        if self.on_event:
            self.on_event("channels_get", channels)

    async def messages_get(self):
        """
        Handles getting messages from server and adding them to UI
        """
        assert self.websocket is not None
        messages = self.data["messages"]

        if self.on_event:
            self.on_event("messages_get", messages)

    async def message_new(self):
        """
        Handles receiving a new user message from the server
        """
        assert self.websocket is not None

        if self.data["channel"] == self.channel:
            message = self.data["message"]
            if self.on_event:
                self.on_event("message_new", message)


async def get_server_info(url: str) -> dict:
    """
    Gets info about a originChats server

    :param url: URL to websocket server
    :type url: str
    :return: Dictionary of handshake
    :rtype: dict[Any, Any]
    """
    async with websockets.connect(url) as websocket:
        response = await websocket.recv()
        await websocket.close(websockets.CloseCode.NORMAL_CLOSURE)
        return json.loads(response)
