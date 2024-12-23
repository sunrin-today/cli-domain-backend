import contextlib
from typing import ClassVar, Any

from aiohttp import ClientSession
from sentry_sdk import capture_exception

from app.core.config import settings
from app.core.error import ErrorCode
from app.core.response import APIError
from app.logger import use_logger

from app.entity import User as UserEntity

_http_log = use_logger("aiohttp-request")
_discord_log = use_logger("discord-request-service")


def check_discord_role(roles: list[str], specific_role_id: int) -> bool:
    return any(role_id == str(specific_role_id) for role_id in roles)


def create_ticket_message(domain_name: str, user: UserEntity, value: dict) -> dict:
    value_string = "\n".join(f"{key}: {value}" for key, value in value.items())
    return {
        "embeds": [
            {
                "title": f"{domain_name} 도메인 등록 요청",
                "description": f"```yaml\n{value_string}\n```",
                "author": {
                    "name": f"{user.nickname} ({user.email})",
                    "icon_url": user.avatar,
                },
                "timestamp": "2024-12-20T05:26:00.000Z",
            }
        ],
        "attachments": [],
    }


INTERNAL_API_VERSION: int = 10


def content_type(response: Any) -> Any:
    if response.content_type == "text/html":
        return response.text()
    with contextlib.suppress(Exception):
        return response.json()
    return response.text()


class DiscordRequester:
    API: ClassVar[str] = f"https://discord.com/api/v{INTERNAL_API_VERSION}"

    def __init__(self) -> None:
        self._session = ClientSession(
            headers={
                "Authorization": f"Bot {settings.DISCORD_BOT_TOKEN}",
            }
        )

    async def request(self, method: str, path: str, **kwargs):
        url = f"{self.API}/{path}"
        async with self._session.request(method, url, **kwargs) as response:
            _http_log.debug(
                "%s %s with %s has returned %s",
                method,
                url,
                kwargs.get("data"),
                response.status,
            )
            data = await content_type(response)

            if 300 > response.status >= 200:
                _http_log.debug("%s %s has received %s", method, url, data)
                return data

            error = APIError(
                status_code=400,
                error_code=ErrorCode.INTERNAL_SERVER_ERROR,
                message="서버에서 요청을 처리할 수 없습니다. 잠시 후 다시 시도해주세요.",
            )
            capture_exception(error)
            _discord_log.info(f"Error: {error}")
            raise error

    async def followup_interaction(self, token: str) -> None:
        data = await self.request(
            "POST", f"/webhooks/{settings.DISCORD_BOT_ID}/{token}/callback", json={}
        )

    async def response_interaction(
        self, interaction_id: str, token: str, data: dict
    ) -> None: ...

    async def send_ticket_message(self, channel_id: str, data: dict) -> None:
        await self.request("POST", f"/channels/{channel_id}/messages", json=data)
