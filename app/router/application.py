import base64
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Query, Depends, status, Request, BackgroundTasks
from fastapi_restful.cbv import cbv
from starlette.responses import RedirectResponse, HTMLResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.deps import get_current_user_entity, get_query_user_entity
from app.entity import User
from app.core.error import ErrorCode
from app.core.response import APIResponse, APIError
from app.router.domain import register_domain_filter
from app.service.cloudflare import CloudflareRequestService
from app.service.container import ServiceContainer
from app.service.domain import DomainService
from app.service.email import EmailRequesterService
from app.service.google import GoogleRequestService
from app.service.localdb import LocalDBService
from app.service.session import LoginSessionService, UserSessionService
from app.service.discord_interaction import DiscordRequester
from app.logger import use_logger
from app.core.redis import settings
from app.core.string import (
    DomainRecordVerify,
    get_main_domain,
    create_vercel_integration_url,
)
from app.service.transfer import DomainTransferService

router = APIRouter(
    prefix="/app",
    tags=["Application"],
    responses={404: {"description": "Not found"}},
)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URI,
)
_log = use_logger("auth-controller")


@cbv(router)
class ApplicationController:

    @router.get("/vercel/entry", description="Vercel Register Entry")
    @limiter.limit("20/minute")
    @inject
    async def vercel_oauth2_entry(
        self,
        request: Request,
        name: str = Query(...),
        credential: tuple[User, str] = Depends(get_query_user_entity),
        localdb_service: LocalDBService = Depends(Provide[ServiceContainer.localdb]),
        cloudflare_service: CloudflareRequestService = Depends(
            Provide[ServiceContainer.cloudflare]
        ),
        domain_service: DomainService = Depends(Provide[ServiceContainer.domain]),
    ) -> RedirectResponse:
        if not register_domain_filter(name):
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message="도메인 등록이 불가능합니다.",
            )
        main_domain = get_main_domain(name)
        available_domains = await localdb_service.available_domains()
        if not main_domain in available_domains:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message=f"{main_domain}은 사용할 수 없습니다.",
            )

        zone_id = await localdb_service.get_zone_id(main_domain)
        is_available = await cloudflare_service.is_available_domain(name, zone_id)
        if not is_available:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message=f"{name}은 사용할 수 없습니다.",
            )

        is_available_ticket = await domain_service.ticket_create_available(
            credential[0]
        )
        if not is_available_ticket:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message="최대 도메인 신청 한도에 도달했습니다.",
            )

        is_exist_ticket = await domain_service.is_exist_ticket(name, credential[0])
        if is_exist_ticket:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message="이미 신청한 도메인입니다.",
            )
        state_string = credential[1] + "/" + name
        encoded_state = base64.b64encode(state_string.encode()).decode()
        return RedirectResponse(url=create_vercel_integration_url(state=encoded_state))

    @router.get("/transfer/accept", description="Transfer Accept")
    @limiter.limit("20/minute")
    @inject
    async def accept_transfer(
        self,
        request: Request,
        background_task: BackgroundTasks,
        code: str = Query(...),
        user: User = Depends(get_query_user_entity),
        transfer_service: DomainTransferService = Depends(
            Provide[ServiceContainer.transfer]
        ),
        discord_service: DiscordRequester = Depends(Provide[ServiceContainer.discord]),
    ) -> HTMLResponse:
        if not code:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_INVITE,
                message="잘못된 Oauth2 요청입니다.",
            )

        invite_entity = await transfer_service.get_transfer_invite(code)
        domain_entity = await transfer_service.accept_transfer_invite(
            invite_entity, user
        )
        background_task.add_task(
            discord_service.create_log_transfer_domain,
            user=user,
            domain=domain_entity,
            target_user_email=user.email,
        )
        return HTMLResponse(
            content=f"<h1>{domain_entity.name} 도메인을 성공적으로 이전했습니다</h1>"
        )
