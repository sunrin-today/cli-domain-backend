import contextlib
from typing import ClassVar, Any

from aiohttp import ClientSession, FormData

from app.core.config import settings
from app.core.error import ErrorCode
from app.core.response import APIError
from app.logger import use_logger

from sentry_sdk import capture_exception

_http_log = use_logger("aiohttp-request")
_vercel_log = use_logger("vercel-request-service")


def content_type(response: Any) -> Any:
    if response.content_type == "text/html":
        return response.text()
    with contextlib.suppress(Exception):
        return response.json()
    return response.text()


class VercelRequestService:
    API: ClassVar[str] = f"https://api.vercel.com"

    def __init__(self) -> None:
        self._session = ClientSession()

    async def request(self, method: str, path: str, **kwargs):
        url = f"{self.API}{path}"
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
                error_code=ErrorCode.DNS_SERVER_ERROR,
                message="DNS 서버에서 요청을 처리할 수 없습니다. 잠시 후 다시 시도해주세요.",
            )
            capture_exception(error)
            _vercel_log.info(f"Error: {data}")
            raise error

    async def create_access_code(self, code: str) -> dict:
        return await self.request(
            "POST",
            "/v2/oauth/access_token",
            data=FormData(
                {
                    "client_id": settings.VERCEL_CLIENT_ID,
                    "client_secret": settings.VERCEL_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": "https://domain.sunrin.kr/api/v1"
                    + "/app/vercel/callback",
                }
            ),
        )

    async def fetch_project(self, access_token: str) -> dict:
        return await self.request(
            "GET",
            "/v1/projects",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

    async def fetch_current_user(self, access_token: str) -> dict:
        return await self.request(
            "GET",
            "/v2/user",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )
