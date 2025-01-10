import uuid
from datetime import timedelta

from fastapi import status
from starlette.websockets import WebSocket

from app.core.error import ErrorCode
from app.core.response import APIError
from app.core.websocket import ConnectionManager

from app.core.string import generate_token
from app.core.redis import manager
from app.logger import use_logger

_login_log = use_logger("login-session-service")


class LoginSessionService:
    KEY = "LOGIN_SESSION"
    EXPIRATION = timedelta(minutes=5)

    def __init__(self, websocket: ConnectionManager) -> None:
        self.redis = manager.get_connection()
        self.subscribe_websocket = websocket

    async def create_new_session(
        self,
        session_id: str | None = None,
        application_url: str | None = None,
        user_id: str | None = None,
    ) -> str:
        if not session_id:
            session_id = str(uuid.uuid4())
        session_data = {"type": "login", "user_id": "", "application_url": ""}
        if application_url:
            session_data["type"] = "application"
            session_data["application_url"] = application_url
        if user_id:
            session_data["user_id"] = user_id
        await self.redis.hmset(f"{self.KEY}:{session_id}", session_data)
        await self.redis.expire(f"{self.KEY}:{session_id}", self.EXPIRATION)
        return session_id

    async def set_session_user(self, session_id: str, user_id: str) -> None:
        await self.redis.hset(f"{self.KEY}:{session_id}", "user_id", user_id)

    async def get_session_user_id(self, session_id: str) -> str | None:
        bytes_value = await self.redis.hget(f"{self.KEY}:{session_id}", "user_id")
        return bytes_value.decode("utf-8") or None

    async def get_session_type(self, session_id: str) -> str:
        bytes_value = await self.redis.hget(f"{self.KEY}:{session_id}", "type")
        return bytes_value.decode("utf-8")

    async def get_session_application_url(self, session_id: str) -> str | None:
        bytes_value = await self.redis.hget(
            f"{self.KEY}:{session_id}", "application_url"
        )
        return bytes_value.decode("utf-8") or None

    async def exist_session(self, session_id: str) -> bool:
        return await self.redis.exists(f"{self.KEY}:{session_id}")

    async def delete_session(self, session_id: str) -> None:
        await self.redis.delete(f"{self.KEY}:{session_id}")

    async def push_token_to_session(self, session_id: str, token: str) -> None:
        if self.subscribe_websocket.exist(session_id):
            await self.subscribe_websocket.send_message(session_id, {"token": token})
            await self.subscribe_websocket.disconnect(session_id)

    def exist_subscriber(self, session_id: str) -> bool:
        return self.subscribe_websocket.exist(session_id)

    async def subscribe_session(self, session_id: str, websocket: WebSocket) -> None:
        if self.exist_subscriber(session_id):
            try:
                await self.subscribe_websocket.disconnect(
                    session_id,
                    code=status.WS_1001_GOING_AWAY,
                    reason="New subscriber is connected",
                )
            except Exception as e:
                pass
        _login_log.info(f"Subscribe session: {session_id}, {websocket.client.host}")
        await self.subscribe_websocket.connect(session_id, websocket)


class UserSessionService:
    KEY = "USER_SESSION"
    EXPIRATION = timedelta(weeks=10)

    def __init__(self) -> None:
        self.redis = manager.get_connection()

    async def create_new_token(self, user_id: str) -> str:
        token = generate_token()
        await self.redis.setex(f"{self.KEY}:{token}", self.EXPIRATION, str(user_id))
        return token

    async def update_token(self, token: str) -> None:
        await self.redis.expire(f"{self.KEY}:{token}", self.EXPIRATION)

    async def get_user_id(self, token: str) -> str:
        bytes_value = await self.redis.get(f"{self.KEY}:{token}")
        if not bytes_value:
            raise APIError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_code=ErrorCode.INVALID_SESSION,
                message="Invalid session token",
            )
        return bytes_value.decode("utf-8")

    async def exist_token(self, token: str) -> bool:
        return await self.redis.exists(f"{self.KEY}:{token}")

    async def delete_token(self, token: str) -> None:
        _login_log.info(f"Delete token: {token}")
        await self.redis.delete(f"{self.KEY}:{token}")
