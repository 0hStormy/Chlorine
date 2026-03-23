import websockets
import json


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