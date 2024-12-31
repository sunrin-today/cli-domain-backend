from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Query, Depends, status, Request, Body, BackgroundTasks
from fastapi_restful.cbv import cbv
from slowapi import Limiter
from starlette.responses import HTMLResponse

from app.core.deps import get_current_user_entity, get_user_token
from app.core.string import get_main_domain, build_domain_record_view
from app.entity import User
from app.core.error import ErrorCode
from app.core.response import APIResponse, APIError
from app.entity.ticket import DomainTicketStatus
from app.router.domain import register_domain_filter
from app.schema.home import TransferDomainDTO
from app.schema.register import RecordDTO
from app.service.cloudflare import CloudflareRequestService
from app.service.container import ServiceContainer
from app.service.discord_interaction import DiscordRequester
from app.service.domain import DomainService
from app.service.email import EmailRequesterService
from app.service.localdb import LocalDBService
from app.logger import use_logger
from app.core.redis import settings
from app.service.transfer import DomainTransferService

router = APIRouter(
    prefix="/transfer",
    tags=["DomainTransfer"],
    responses={404: {"description": "Not found"}},
)
limiter = Limiter(
    key_func=get_user_token,
    storage_uri=settings.REDIS_URI,
)
_log = use_logger("domain-transfer-controller")


@cbv(router)
class DomainTransferController:

    @router.post(
        "/create",
        description="TTL을 1로 설정하면 Cloudflare에서 AUTO로 설정됩니다.",
    )
    @limiter.limit("20/minute")
    @inject
    async def transfer_record(
        self,
        request: Request,
        background_task: BackgroundTasks,
        user: User = Depends(get_current_user_entity),
        data: TransferDomainDTO = Body(...),
        localdb_service: LocalDBService = Depends(Provide[ServiceContainer.localdb]),
        domain_service: DomainService = Depends(Provide[ServiceContainer.domain]),
        email_service: EmailRequesterService = Depends(Provide[ServiceContainer.email]),
        discord_service: DiscordRequester = Depends(Provide[ServiceContainer.discord]),
        transfer_service: DomainTransferService = Depends(
            Provide[ServiceContainer.transfer]
        ),
    ) -> APIResponse[dict]:
        if register_domain_filter(data.name):
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message="도메인 등록이 불가능합니다.",
            )
        main_domain = get_main_domain(data.name)
        available_domains = await localdb_service.available_domains()
        if not main_domain in available_domains:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message=f"{main_domain}은 사용할 수 없습니다.",
            )
        domain_entity = await domain_service.get_domain(user, data.name)
        if not domain_entity:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message=f"{data.name}은 사용할 수 없습니다.",
            )

        invite_entity = await transfer_service.create_transfer_link(
            user=user, domain=domain_entity, transfer_user_email=str(data.user_email)
        )
        await email_service.send_transfer_invite_email(
            to_email=str(data.user_email),
            domain_name=data.name,
            user_name=user.nickname,
            transfer_entity_id=str(invite_entity.id),
        )
        background_task.add_task(
            discord_service.create_log_transfer_invite,
            user=user,
            domain=domain_entity,
            target_user_email=str(data.user_email),
        )
        return APIResponse(
            data={"email": str(data.user_email)},
            message="도메인 초대링크 전송이 완료되었습니다.",
        )

    @router.get("/accept")
    async def accept_transfer(
        self,
        code: str = Query(None, description="도메인 초대 코드"),
    ) -> HTMLResponse:
        if not code:
            return HTMLResponse(
                content="<h1>Sunrin Today Domain</h1><br>"
                "<p>도메인 초대 코드가 유효하지 않습니다</p>"
            )
        return HTMLResponse(content="도메인 초대 수락 페이지")
