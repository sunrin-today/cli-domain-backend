from functools import lru_cache

from dependency_injector.wiring import inject, Provide
from fastapi import status

from app.core.error import ErrorCode
from app.core.response import APIError
from app.entity.user import User as UserEntity
from app.entity.ticket import DomainTicket as DomainTicketEntity, DomainTicketStatus
from app.entity.domain import Domain as DomainEntity

from app.core.config import settings
from app.schema.register import RecordDTO
from app.service.discord_interaction import DiscordRequester


class DomainService:

    @staticmethod
    async def ticket_create_available(user: UserEntity | str) -> int:
        if isinstance(user, str):
            user: UserEntity = await UserEntity.get(id=user)
        await user.fetch_related("domains")
        ticket_count = await DomainTicketEntity.filter(
            user=user.id, status=DomainTicketStatus.PENDING
        ).count()
        domain_count = len(user.domains)
        if ticket_count + domain_count >= settings.USER_DOMAIN_MAXIMUM:
            return False
        return True

    @staticmethod
    async def is_exist_ticket(domain: str, user_only: UserEntity | str = None) -> bool:
        if user_only:
            if isinstance(user_only, str):
                user_only: UserEntity = await UserEntity.get(id=user_only)

            return await DomainTicketEntity.filter(
                user=user_only.id, name=domain
            ).exists()

        return await DomainTicketEntity.exists(name=domain)

    @staticmethod
    async def create_ticket(
        record_data: RecordDTO, user: UserEntity | str
    ) -> DomainTicketEntity:
        if isinstance(user, str):
            user: UserEntity = await UserEntity.get(id=user)

        ticket = await DomainTicketEntity.create(
            name=record_data.name,
            content=record_data.content,
            record_type=record_data.type,
            data=record_data.data,
            proxied=record_data.proxied,
            ttl=record_data.ttl,
        )
        await user.tickets.add(ticket)
        return ticket

    @staticmethod
    async def approved_ticket(
        ticket_id: str,
    ) -> tuple[DomainTicketEntity, DomainEntity]:
        ticket = await DomainTicketEntity.get(id=ticket_id)
        new_domain_entity = await DomainEntity.create(
            name=ticket.name,
            content=ticket.content,
            record_type=ticket.record_type,
            data=ticket.data,
            proxied=ticket.proxied,
            ttl=ticket.ttl,
        )
        ticket.status = DomainTicketStatus.APPROVED
        await ticket.save()
        return ticket, new_domain_entity

    @staticmethod
    async def reject_ticket(
        ticket_id: str,
    ) -> DomainTicketEntity:
        ticket = await DomainTicketEntity.get(id=ticket_id)
        ticket.status = DomainTicketStatus.REJECTED
        await ticket.save()
        return ticket

    @staticmethod
    async def get_domain(user: UserEntity, domain_name: str) -> DomainEntity | None:
        return await DomainEntity.filter(user=user.id, name=domain_name).first()

    @staticmethod
    async def update_domain_entity(
        domain: DomainEntity, record_data: RecordDTO
    ) -> DomainEntity:
        domain.content = record_data.content
        domain.record_type = record_data.type
        domain.data = record_data.data
        domain.proxied = record_data.proxied
        domain.ttl = record_data.ttl
        await domain.save()
        return domain

    @staticmethod
    async def get_ticket(
        ticket_id: str, /, user_only: UserEntity | None = None
    ) -> DomainTicketEntity:
        if user_only:
            ticket_entity = await DomainTicketEntity.get_or_none(
                id=ticket_id, user=user_only.id
            )
        else:
            ticket_entity = await DomainTicketEntity.get_or_none(id=ticket_id)
        if not ticket_entity:
            raise APIError(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.TICKET_NOT_FOUND,
                message="티켓을 찾을 수 없습니다.",
            )
        return ticket_entity

    @staticmethod
    @lru_cache(maxsize=500)
    async def get_status() -> dict:
        return {
            "ticket": {
                "pending": await DomainTicketEntity.filter(
                    status=DomainTicketStatus.PENDING
                ).count(),
                "approved": await DomainTicketEntity.filter(
                    status=DomainTicketStatus.APPROVED
                ).count(),
                "rejected": await DomainTicketEntity.filter(
                    status=DomainTicketStatus.REJECTED
                ).count(),
            },
            "domain": {
                "total": await DomainEntity.all().count(),
            },
            "user": {
                "total": await UserEntity.all().count(),
            },
        }
