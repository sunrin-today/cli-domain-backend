from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Query, Depends, status, Request, Body
from fastapi_restful.cbv import cbv
from slowapi import Limiter

from app.core.deps import get_current_user_entity, get_user_token
from app.core.string import get_main_domain, build_domain_record_view
from app.entity import User
from app.core.error import ErrorCode
from app.core.response import APIResponse, APIError
from app.entity.ticket import DomainTicketStatus
from app.schema.home import TransferDomainDTO
from app.schema.register import RecordDTO
from app.service.cloudflare import CloudflareRequestService
from app.service.container import ServiceContainer
from app.service.discord_interaction import DiscordRequester
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


def register_domain_filter(domain_name: str):
    parts = domain_name.split(".")
    if len(parts) <= 2:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
            message="Invalid domain name",
        )
    subdomain = ".".join(parts[:-2])
    subdomain_parts = subdomain.split(".")
    if len(subdomain_parts) > 1:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
            message="Not allowed this subdomain",
        )
    if "*" in subdomain:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
            message="Not allowed wildcard domain",
        )
    return True


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

    @router.post(
        "/delete",
        description="도메인을 삭제합니다.",
    )
    @inject
    async def delete_record(
        self,
        domain: str = Body(..., embed=True),
        user: User = Depends(get_current_user_entity),
        localdb_service: LocalDBService = Depends(Provide[ServiceContainer.localdb]),
        domain_service: DomainService = Depends(Provide[ServiceContainer.domain]),
        cloudflare_service: CloudflareRequestService = Depends(
            Provide[ServiceContainer.cloudflare]
        ),
        discord_service: DiscordRequester = Depends(Provide[ServiceContainer.discord]),
    ) -> APIResponse[dict]:
        if register_domain_filter(domain):
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message="도메인 등록이 불가능합니다.",
            )
        main_domain = get_main_domain(domain)
        available_domains = await localdb_service.available_domains()
        if not main_domain in available_domains:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message=f"{main_domain}은 사용할 수 없습니다.",
            )
        zone_id = await localdb_service.get_zone_id(main_domain)
        domain_entity = await domain_service.get_domain(user, domain)
        if not domain_entity:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message=f"{domain} 도메인을 찾을 수 없습니다",
            )
        await cloudflare_service.delete_record(zone_id, domain_entity.record_id)
        await discord_service.create_log_delete_domain(
            user=user,
            domain=domain_entity,
        )
        await domain_entity.delete()
        return APIResponse(
            data={
                "id": domain_entity.id,
                "name": domain_entity.name,
                "createdAt": domain_entity.created_at,
                "updatedAt": domain_entity.updated_at,
            },
            message="도메인 삭제가 완료되었습니다.",
        )

    @router.post(
        "/update",
        description="TTL을 1로 설정하면 Cloudflare에서 AUTO로 설정됩니다.",
    )
    @limiter.limit("20/minute")
    @inject
    async def update_record(
        self,
        request: Request,
        user: User = Depends(get_current_user_entity),
        data: RecordDTO = Body(...),
        localdb_service: LocalDBService = Depends(Provide[ServiceContainer.localdb]),
        cloudflare_service: CloudflareRequestService = Depends(
            Provide[ServiceContainer.cloudflare]
        ),
        domain_service: DomainService = Depends(Provide[ServiceContainer.domain]),
        discord_service: DiscordRequester = Depends(Provide[ServiceContainer.discord]),
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

        zone_id = await localdb_service.get_zone_id(main_domain)
        domain_entity = await domain_service.get_domain(user, data.name)
        if not domain_entity:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message=f"{data.name}은 사용할 수 없습니다.",
            )
        await domain_service.update_domain_entity(domain_entity, data)
        await cloudflare_service.update_record(
            zone_id=zone_id,
            record_id=domain_entity.record_id,
            data={
                "name": data.name,
                "content": data.content,
                "type": data.type,
                "ttl": data.ttl,
                "proxied": data.proxied,
            },
        )
        await discord_service.create_log_update_domain(
            user=user,
            domain=domain_entity,
            data={
                "name": data.name,
                "content": data.content,
                "type": data.type,
                "ttl": data.ttl,
                "proxied": data.proxied,
            },
        )
        return APIResponse(
            data={
                "id": domain_entity.id,
                "name": domain_entity.name,
                "createdAt": domain_entity.created_at,
                "updatedAt": domain_entity.updated_at,
                "data": data,
            },
            message="도메인 업데이트가 완료되었습니다.",
        )

    @router.post(
        "/register",
        description="TTL을 1로 설정하면 Cloudflare에서 AUTO로 설정됩니다.",
    )
    @limiter.limit("20/minute")
    @inject
    async def register_domain(
        self,
        request: Request,
        user: User = Depends(get_current_user_entity),
        data: RecordDTO = Body(...),
        localdb_service: LocalDBService = Depends(Provide[ServiceContainer.localdb]),
        cloudflare_service: CloudflareRequestService = Depends(
            Provide[ServiceContainer.cloudflare]
        ),
        domain_service: DomainService = Depends(Provide[ServiceContainer.domain]),
        discord_service: DiscordRequester = Depends(Provide[ServiceContainer.discord]),
    ) -> APIResponse[dict]:
        if not register_domain_filter(data.name):
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

        zone_id = await localdb_service.get_zone_id(main_domain)
        is_available = await cloudflare_service.is_available_domain(data.name, zone_id)
        if not is_available:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message=f"{data.name}은 사용할 수 없습니다.",
            )

        is_available_ticket = await domain_service.ticket_create_available(user)
        if not is_available_ticket:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message="최대 도메인 신청 한도에 도달했습니다.",
            )

        is_exist_ticket = await domain_service.is_exist_ticket(data.name, user)
        if is_exist_ticket:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message="이미 신청한 도메인입니다.",
            )

        ticket = await domain_service.create_ticket(
            record_data=data,
            user=user,
        )
        domain_record_view = build_domain_record_view(
            record_data=data,
        )
        await discord_service.send_ticket_message(
            domain_name=data.name,
            user=user,
            record_value=domain_record_view,
            ticket_id=str(ticket.id),
        )
        return APIResponse(
            data={
                "ticket": {
                    "id": ticket.id,
                    "name": ticket.name,
                    "content": ticket.content,
                    "data": ticket.data,
                    "proxied": ticket.proxied,
                    "ttl": ticket.ttl,
                    "createdAt": ticket.created_at,
                }
            },
            message="도메인 신청이 완료되었습니다.",
        )

    @router.get("/")
    @inject
    async def get_domain(
        self, user: User = Depends(get_current_user_entity)
    ) -> APIResponse[dict]:
        await user.fetch_related("domains")
        return APIResponse(
            data={
                "domains": [
                    {
                        "id": domain.id,
                        "name": domain.name,
                        "createdAt": domain.created_at,
                        "updatedAt": domain.updated_at,
                    }
                    for domain in user.domains
                ]
            },
            message="도메인 목록 조회가 완료되었습니다.",
        )

    @router.get("/tickets")
    @inject
    async def get_tickets(
        self,
        user: User = Depends(get_current_user_entity),
        ticket_filter: str = Query("filter"),
    ) -> APIResponse[dict]:
        if ticket_filter == "pending":
            filtered_tickets = await user.tickets.filter(
                status=DomainTicketStatus.PENDING
            )
        elif ticket_filter == "approved":
            filtered_tickets = await user.tickets.filter(
                status=DomainTicketStatus.APPROVED
            )
        elif ticket_filter == "rejected":
            filtered_tickets = await user.tickets.filter(
                status=DomainTicketStatus.REJECTED
            )
        else:
            await user.fetch_related("tickets")
            filtered_tickets = user.tickets

        return APIResponse(
            data={
                "tickets": [
                    {
                        "id": ticket.id,
                        "name": ticket.name,
                        "content": ticket.content,
                        "data": ticket.data,
                        "proxied": ticket.proxied,
                        "ttl": ticket.ttl,
                        "createdAt": ticket.created_at,
                        "status": ticket.status,
                    }
                    for ticket in filtered_tickets
                ]
            },
            message="도메인 티켓 목록 조회가 완료되었습니다.",
        )

    @router.get("/ticket/{ticket_id}/close")
    @inject
    async def close_ticket(
        self,
        ticket_id: str,
        user: User = Depends(get_current_user_entity),
        domain_service: DomainService = Depends(Provide[ServiceContainer.domain]),
    ) -> APIResponse[dict]:
        ticket = await domain_service.get_ticket(ticket_id, user_only=user)
        if not ticket:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.DOMAIN_NOT_ALLOWED,
                message="티켓을 찾을 수 없습니다.",
            )
        await ticket.delete()
        return APIResponse(
            data={"id": ticket_id},
            message="도메인 티켓이 종료되었습니다.",
        )

    @router.get("/ticket/{ticket_id}/status")
    @inject
    async def get_ticket_status(
        self,
        ticket_id: str,
        user: User = Depends(get_current_user_entity),
        domain_service: DomainService = Depends(Provide[ServiceContainer.domain]),
    ) -> APIResponse[dict]:
        ticket = await domain_service.get_ticket(ticket_id, user_only=user)
        return APIResponse(
            data={
                "id": ticket.id,
                "status": ticket.status.name.lower(),
            },
            message="도메인 티켓 상태 조회가 완료되었습니다.",
        )
