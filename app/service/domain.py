from pyasn1_modules.rfc7906 import Register

from app.entity import DomainTicket
from app.entity.user import User as UserEntity
from app.entity.ticket import DomainTicket as DomainTicketEntity, DomainRecordType

from app.core.config import settings
from app.schema.register import RecordDTO


class DomainService:

    @staticmethod
    async def ticket_create_available(user: UserEntity | str) -> int:
        if isinstance(user, str):
            user: UserEntity = await UserEntity.get(id=user)
        await user.fetch_related("tickets", "domains")
        ticket_count = len(user.tickets)
        domain_count = len(user.domains)
        if ticket_count + domain_count >= settings.USER_DOMAIN_MAXIMUM:
            return False
        return True

    @staticmethod
    async def is_exist_ticket(domain: str, user_only: UserEntity | str = None) -> bool:
        if user_only:
            if isinstance(user_only, str):
                user_only: UserEntity = await UserEntity.get(id=user_only)

            return await DomainTicket.filter(users=user_only.id, name=domain).exists()

        return await DomainTicket.exists(name=domain)

    @staticmethod
    async def create_ticket(
        record_data: RecordDTO, user: UserEntity | str
    ) -> DomainTicketEntity:
        if isinstance(user, str):
            user: UserEntity = await UserEntity.get(id=user)

        ticket = await DomainTicket.create(
            name=record_data.name,
            content=record_data.content,
            record_type=record_data.type,
            data=record_data.data,
            proxied=record_data.proxied,
            ttl=record_data.ttl,
        )
        await user.tickets.add(ticket)
        return ticket
