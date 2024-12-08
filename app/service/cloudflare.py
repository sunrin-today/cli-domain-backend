import contextlib
from typing import ClassVar, Any

import sentry_sdk
from aiohttp import ClientSession

from app.core.config import settings
from app.core.error import ErrorCode
from app.core.response import APIError
from app.logger import use_logger

from sentry_sdk import capture_exception

_http_log = use_logger("aiohttp-request")
_cf_log = use_logger("cloudflare-request-service")

INTERNAL_API_VERSION: int = 4


def content_type(response: Any) -> Any:
    if response.content_type == "text/html":
        return response.text()
    with contextlib.suppress(Exception):
        return response.json()
    return response.text()


class CloudflareRequestService:
    API: ClassVar[str] = f"https://api.cloudflare.com/client/v{INTERNAL_API_VERSION}"

    def __init__(self) -> None:
        self._session = ClientSession(
            headers={
                "Authorization": f"Bearer {settings.CLOUDFLARE_API_TOKEN}",
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
                error_code=ErrorCode.DNS_SERVER_ERROR,
                message="DNS 서버에서 요청을 처리할 수 없습니다. 잠시 후 다시 시도해주세요.",
            )
            capture_exception(error)
            _cf_log.info(f"Error: {error}")
            raise error

    async def available_zones(self):
        data = await self.request("GET", "/zones")
        if settings.CLOUDFLARE_ZONE_ID not in data:
            error = APIError(
                status_code=400,
                error_code=ErrorCode.DNS_ZONE_NOT_FOUND,
                message="DNS Zone이 존재하지 않습니다.",
            )
            capture_exception(error)
            _cf_log.info(f"Error: {error}")
            raise error

    async def fetch_zones(self):
        return await self.request("GET", "/zones")

    async def fetch_record(self, zone_id: str):
        return await self.request("GET", f"/zones/{zone_id}/dns_records")

    async def is_available_domain(
        self,
        domain: str,
        zone_id: str,
    ) -> bool:
        records = await self.fetch_record(zone_id)
        return domain not in [record["name"] for record in records["result"]]
