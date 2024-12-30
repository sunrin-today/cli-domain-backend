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
