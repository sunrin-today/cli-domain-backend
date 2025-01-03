from fastapi import WebSocket
from app.logger import use_logger

logger = use_logger("websocket")


class ConnectionManager:
    def __init__(self):
        self.subscribe_websocket: dict[str, WebSocket] = {}

    def get_all_connection(self):
        return self.subscribe_websocket

    def exist(self, session_id: str):
        return session_id in self.subscribe_websocket

    async def connect(self, session_id: str, websocket: WebSocket):
        self.subscribe_websocket[session_id] = websocket

    async def send_message(self, session_id: str, message: dict):
        try:
            await self.subscribe_websocket[session_id].send_json(message)
        except RuntimeError:
            logger.info(f"Session {session_id} is already closed")
            pass

    async def disconnect(self, session_id: str, **kwargs):
        await self.subscribe_websocket[session_id].close(**kwargs)
        del self.subscribe_websocket[session_id]

    async def get_connection(self, session_id: str):
        return self.subscribe_websocket[session_id]
