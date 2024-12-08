from app.entity import DomainTicket


class DomainService:

    @staticmethod
    async def is_exist_ticket(domain: str) -> bool:
        return await DomainTicket.exists(name=domain)
