import json
import websockets
import config
import log


def get_selected_server(path: str = config.CONFIG_PATH) -> str:
    """
    Gets selected server by user in config file

    :param path: Path to config file
    :type path: str
    :return: Websocket server address
    :rtype: str
    """
    servers = config.get_value(path, "servers")
    server_index = config.get_value(path, "selected_server")

    assert isinstance(servers, list)
    assert isinstance(server_index, int)

    selected_server = servers[server_index]
    return selected_server


async def get_server_info(server: str) -> dict:
    async with websockets.connect(server) as websocket:
        handshake = await websocket.recv()
        await websocket.close(1000, "")
        return json.loads(handshake)


class Handle:
    def __init__(self, address: str = get_selected_server()) -> None:
        self.address = address

    async def start(self):
        async with websockets.connect(self.address) as websocket:
            handshake = await websocket.recv()
            log.info(f"Handshake received {handshake}")
