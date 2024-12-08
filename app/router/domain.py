import uuid
from zoneinfo import available_timezones

import aiogoogle.excs
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Query, Depends, status, Request, Body
from fastapi_restful.cbv import cbv
from starlette.responses import RedirectResponse, HTMLResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.deps import get_current_user_entity, get_user_token
from app.core.string import get_main_domain
from app.entity import User
from app.core.error import ErrorCode
from app.core.response import APIResponse, APIError
from app.schema.register import (
    RecordValueType,
    RecordAAAAValueDTO,
    RecordAValueDTO,
    RegisterDomainDTO,
)
from app.service.cloudflare import CloudflareRequestService
from app.service.container import ServiceContainer
from app.service.domain import DomainService
from app.service.google import GoogleRequestService
from app.service.localdb import LocalDBService
from app.service.session import LoginSessionService, UserSessionService
from app.logger import use_logger
from app.core.redis import settings

router = APIRouter(
    prefix="/domain",
    tags=["Domain"],
    responses={404: {"description": "Not found"}},
)
limiter = Limiter(
    key_func=get_user_token,
    storage_uri=settings.REDIS_URI,
)
_log = use_logger("domain-controller")


@cbv(router)
class DomainController:

    @router.get("/available")
    @inject
    async def available_domain(
        self,
        localdb_service: LocalDBService = Depends(Provide[ServiceContainer.localdb]),
    ) -> APIResponse[dict]:
        available_domains = await localdb_service.available_domains()
        return APIResponse(
            data={
                "domains": available_domains,
            },
            message="사용가능한 도메인입니다.",
        )

    @router.get("/exist")
    @inject
    async def exist_domain(
        self,
        name: str = Query(...),
        user: User = Depends(get_current_user_entity),
        localdb_service: LocalDBService = Depends(Provide[ServiceContainer.localdb]),
        cloudflare_service: CloudflareRequestService = Depends(
            Provide[ServiceContainer.cloudflare]
        ),
    ) -> APIResponse[dict]:
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
        return APIResponse(
            data={
                "isAvailable": is_available,
            },
            message=(
                f"{name}은 사용할 수 있습니다."
                if is_available
                else f"{name}은 사용할 수 없습니다."
            ),
        )

    @router.post("/register")
    @limiter.limit("20/minute")
    @inject
    async def register_domain(
        self,
        request: Request,
        user: User = Depends(get_current_user_entity),
        data: RegisterDomainDTO = Body(...),
        localdb_service: LocalDBService = Depends(Provide[ServiceContainer.localdb]),
        cloudflare_service: CloudflareRequestService = Depends(
            Provide[ServiceContainer.cloudflare]
        ),
        domain_service: DomainService = Depends(Provide[ServiceContainer.domain]),
    ) -> APIResponse[dict]:
        main_domain = get_main_domain(data.name)
        available_domains = await localdb_service.available_domains()
        if not main_domain in available_domains:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message=f"{main_domain}은 사용할 수 없습니다.",
            )

        zone_id = await localdb_service.get_zone_id(main_domain)
        is_available = await cloudflare_service.is_available_domain(data.name, zone_id)
        if not is_available:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message=f"{data.name}은 사용할 수 없습니다.",
            )

        is_available_ticket = await domain_service.is_exist_ticket(domain=data.name)
        if is_available_ticket:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_ALREADY_EXIST,
                message=f"{data.name}은 이미 등록된 도메인입니다.",
            )

        # register domain process

    @router.get("/")
    @inject
    async def get_domain(
        self, user: User = Depends(get_current_user_entity)
    ) -> APIResponse[dict]:
        await user.fetch_related("domains")
        return APIResponse(
            data={
                "domains": [
                    [
                        {
                            "id": domain.id,
                            "name": domain.name,
                            "createdAt": domain.created_at,
                            "updatedAt": domain.updated_at,
                        }
                        for domain in user.domains
                    ]
                    for domain in user.domains
                ]
            },
            message="Domain list",
        )
