import contextlib
from typing import ClassVar, Any

from aiohttp import ClientSession, BasicAuth
from sentry_sdk import capture_exception

from app.core.response import APIError
from app.core.error import ErrorCode
from app.core.config import settings
from app.logger import use_logger

_http_log = use_logger("aiohttp-request")
_email_log = use_logger("email-request-service")

INTERNAL_API_VERSION: int = 1


def content_type(response: Any) -> Any:
    if response.content_type == "text/html":
        return response.text()
    with contextlib.suppress(Exception):
        return response.json()
    return response.text()


class EmailRequesterService:
    API: ClassVar[str] = f"https://api.forwardemail.net/v{INTERNAL_API_VERSION}"

    def __init__(self):
        self._session = ClientSession(
            auth=BasicAuth(
                login=settings.EMAIL_API_KEY,
            )
        )

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
                error_code=ErrorCode.INTERNAL_SERVER_ERROR,
                message="이메일 서버에서 요청을 처리할 수 없습니다. 잠시 후 다시 시도해주세요.",
            )
            capture_exception(error)
            _email_log.info(f"Error: {data}")
            raise error

    async def send_email(self, to_email: str, subject: str, text: str) -> None:
        email_data = {
            "from": "Sunrin Domain <" + settings.EMAIL_SENDER_ADDRESS + ">",
            "to": to_email,
            "subject": subject,
            "text": text,
        }
        await self.request("POST", "/emails", json=email_data)

    async def send_approved_email(self, to_email: str, domain_name: str) -> None:
        subject = f"[Sunrin Domain] {domain_name} 도메인 승인됨"
        text = [
            f"안녕하세요. 선린 도메인입니다.",
            f"{domain_name}이 승인되었습니다. 이제 해당 도메인을 사용할 수 있습니다.",
            f"감사합니다.",
            f"Sunrin Domain 드림",
        ]
        await self.send_email(to_email, subject, "\n".join(text))

    async def send_rejected_email(
        self, to_email: str, domain_name: str, reason: str | None = None
    ) -> None:
        if not reason:
            reason = f"관리자가 도메인 신청을 거절함."
        subject = f"[Sunrin Domain] {domain_name} 도메인 거절됨"
        text = [
            f"안녕하세요. 선린 도메인입니다.",
            f"{domain_name}이 거절되었습니다. 사유: {reason}",
            "자세한 문의는 domain@sunrin.kr로 문의해주세요.",
            f"감사합니다.",
            f"Sunrin Domain 드림",
        ]
        await self.send_email(to_email, subject, "\n".join(text))

    async def send_failed_email(
        self, to_email: str, domain_name: str, reason: str | None = None
    ) -> None:
        if not reason:
            reason = f"서비스 처리 도중 오류 발생"
        subject = f"[Sunrin Domain] {domain_name} 도메인 생성 실패"
        text = [
            f"안녕하세요. 선린 도메인입니다.",
            f"{domain_name}이 생성에 실패했습니다. 사유: {reason}",
            "자세한 문의는 domain@sunrin.kr로 문의해주세요.",
            f"감사합니다.",
            f"Sunrin Domain 드림",
        ]
        await self.send_email(to_email, subject, "\n".join(text))

    async def send_welcome_email(self, to_email: str, name: str) -> None:
        subject = f"[Sunrin Domain] {name}님, 환영합니다!"
        text = [
            f"안녕하세요. 선린 도메인입니다.",
            f"{name}님, 환영합니다! 선린 도메인 서비스에 가입해 주셔서 감사합니다.",
            "자세한 문의는 domain@sunrin.kr로 문의해주세요.",
            "감사합니다.",
            f"Sunrin Domain 드림",
        ]
        await self.send_email(to_email, subject, "\n".join(text))

    async def send_transfer_invite_email(
        self,
        to_email: str,
        domain_name: str,
        user_name: str,
        transfer_entity_id: str,
    ) -> None:
        subject = f"[Sunrin Domain] {domain_name} 도메인 이전 초대"
        text = [
            f"안녕하세요. 선린 도메인입니다.",
            f"{user_name}님이 {domain_name} 도메인을 이전하고자 합니다.",
            f"https://domain-api.sunrin.kr/api/v1/transfer/accept?code={transfer_entity_id}",
            "위 링크는 메인을 클릭하면 도메인 이전을 수락할 수 있으며 일주일 후에 만료됩니다.",
            "자세한 문의는 domain@sunrin.kr로 문의해주세요.",
            "감사합니다.",
            f"Sunrin Domain 드림",
        ]
        await self.send_email(to_email, subject, "\n".join(text))
