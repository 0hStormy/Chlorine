import requests
import websockets
import json
import config


class Server:
    def __init__(self, url: str, on_event=None) -> None:
        """
        originChats server instance

        :param url: URL to websocket server
        """
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
        async with websockets.connect(self.url) as websocket:
            self.websocket = websocket
            commands = {
                "handshake": self.handshake,
                "auth_success": self.auth_success,
                "ready": self.ready,
                "channels_get": self.channels_get,
                "messages_get": self.messages_get
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
