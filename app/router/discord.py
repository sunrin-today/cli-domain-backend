from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Request, Depends
from fastapi_restful.cbv import cbv
from fastapi import HTTPException, BackgroundTasks
from slowapi import Limiter
from slowapi.util import get_remote_address
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from discord import Interaction

from app.core.string import get_main_domain
from app.schema.discord import (
    InteractionResponse,
    InteractionCallbackType,
    InteractionType,
    create_interaction_response,
)
from app.logger import use_logger
from app.core.redis import settings
from app.service.cloudflare import CloudflareRequestService
from app.service.container import ServiceContainer
from app.service.discord_interaction import (
    DiscordRequester,
    TicketRespondDiscordComponent,
)
from app.service.discord_old import check_discord_role
from app.service.domain import DomainService
from app.service.email import EmailRequesterService
from app.entity import DomainTicket as DomainTicketEntity
from app.service.localdb import LocalDBService

router = APIRouter(
    prefix="/discord",
    tags=["DiscordInteraction"],
    responses={404: {"description": "Not found"}},
)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URI,
)
_log = use_logger("discord-controller")

verify_key = VerifyKey(bytes.fromhex(settings.DISCORD_PUBLIC_KEY))


async def verify_discord_signature(request: Request):
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")
    body = await request.body()

    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Invalid request signature")

    try:
        verify_key.verify(
            f"{timestamp}{body.decode()}".encode(), bytes.fromhex(signature)
        )
    except BadSignatureError:
        raise HTTPException(status_code=401, detail="Invalid request signature")


@cbv(router)
class DiscordController:
    def __init__(self, *args, **kwargs) -> None:
        self.commands = {
            "approve": self.approve_ticket,
            "reject": self.reject_ticket,
        }
        super().__init__(*args, **kwargs)

    async def process_interaction(
        self,
        interaction: Interaction,
        task_manager: BackgroundTasks,
        requester: DiscordRequester,
    ) -> InteractionResponse | dict:
        command_id, data = interaction.data["custom_id"].split("@")
        if not self.commands.get(command_id):
            return requester.response.send_message(
                content="명령어를 찾을 수 없습니다.",
                ephemeral=True,
            )

        return await self.commands[command_id](
            interaction=interaction,
            task_manager=task_manager,
            client=requester,
            ticket_id=data,
        )

    @staticmethod
    @inject
    async def _approve_ticket(
        client: DiscordRequester,
        ticket_id: str,
        email_service: EmailRequesterService = Depends(Provide[ServiceContainer.email]),
        cloudflare_service: CloudflareRequestService = Depends(
            Provide[ServiceContainer.cloudflare]
        ),
        domain_service: DomainService = Depends(Provide[ServiceContainer.domain]),
        localdb_service: LocalDBService = Depends(Provide[ServiceContainer.localdb]),
    ) -> dict:
        if not await DomainTicketEntity.exists(id=ticket_id):
            return client.response.send_message(
                content="티켓을 찾을 수 없습니다.",
            )
        ticket_entity, domain_entity = await domain_service.approved_ticket(ticket_id)
        main_domain = get_main_domain(domain_entity.name)
        target_zone_id = await localdb_service.get_zone_id(main_domain)
        await ticket_entity.fetch_related("user")
        target_user = await ticket_entity.user.all()
        await target_user[0].domains.add(domain_entity)
        record_created_data = await cloudflare_service.create_record(
            zone_id=target_zone_id,
            data={
                "name": ticket_entity.name,
                "content": ticket_entity.content,
                "type": ticket_entity.record_type,
                "ttl": int(ticket_entity.ttl),
                "proxied": ticket_entity.proxied,
            },
            entity_id=domain_entity.id,
        )
        record_zone_id = record_created_data["result"]["id"]
        domain_entity.record_id = record_zone_id
        await domain_entity.save()
        if record_created_data["success"] is False:
            await client.create_log_service_error(
                user=target_user[0],
                error_name="Cloudflare Record 생성 실패",
                description=f"Ticket ID: {ticket_id}",
                data=record_created_data,
            )
            await email_service.send_failed_email(
                to_email=target_user[0].email,
                domain_name=ticket_entity.name,
                reason="Cloudflare 오류, Ticket ID: " + ticket_id,
            )
        else:
            await client.create_log_new_domain(
                user=target_user[0],
                domain=domain_entity,
                ticket=ticket_entity,
                data={
                    "name": ticket_entity.name,
                    "content": ticket_entity.content,
                    "type": ticket_entity.record_type,
                    "ttl": int(ticket_entity.ttl),
                    "proxied": ticket_entity.proxied,
                },
            )
            await email_service.send_approved_email(
                to_email=target_user[0].email,
                domain_name=ticket_entity.name,
            )

    @staticmethod
    @inject
    async def _reject_ticket(
        client: DiscordRequester,
        ticket_id: str,
        email_service: EmailRequesterService = Depends(Provide[ServiceContainer.email]),
        domain_service: DomainService = Depends(Provide[ServiceContainer.domain]),
    ) -> dict:
        if not await DomainTicketEntity.exists(id=ticket_id):
            return client.response.send_message(
                content="티켓을 찾을 수 없습니다.",
            )
        ticket_entity = await domain_service.reject_ticket(ticket_id)
        await ticket_entity.fetch_related("user")
        target_user = await ticket_entity.user.all()
        await client.create_log_rejected_domain(
            user=target_user[0],
            ticket=ticket_entity,
            data={
                "name": ticket_entity.name,
                "content": ticket_entity.content,
                "type": ticket_entity.record_type,
                "ttl": int(ticket_entity.ttl),
                "proxied": ticket_entity.proxied,
            },
        )
        await email_service.send_rejected_email(
            to_email=target_user[0].email,
            domain_name=ticket_entity.name,
        )

    async def approve_ticket(
        self,
        interaction: Interaction,
        task_manager: BackgroundTasks,
        client: DiscordRequester,
        ticket_id: str,
    ) -> dict:
        previous_embed = interaction.message.embeds[0]
        previous_embed.title = "✅ " + previous_embed.title.replace("요청", "승인됨")
        component = TicketRespondDiscordComponent.success(ticket_id)
        task_manager.add_task(self._approve_ticket, client, ticket_id)
        return client.response.edit_message(
            content=f"승인되었습니다. (유저: {interaction.user.name})",
            embed=previous_embed,
            view=component,
        )

    async def reject_ticket(
        self,
        interaction: Interaction,
        task_manager: BackgroundTasks,
        client: DiscordRequester,
        ticket_id: str,
    ) -> dict:
        previous_embed = interaction.message.embeds[0]
        previous_embed.title = "❌ " + previous_embed.title.replace("요청", "거절됨")
        component = TicketRespondDiscordComponent.reject(ticket_id)
        task_manager.add_task(self._reject_ticket, client, ticket_id)
        return client.response.edit_message(
            content=f"거절했습니다. (유저: {interaction.user.name})",
            embed=previous_embed,
            view=component,
        )

    @router.post("/interaction")
    @inject
    async def interaction(
        self,
        request: Request,
        background_tasks: BackgroundTasks,
        discord_requester: DiscordRequester = Depends(
            Provide[ServiceContainer.discord]
        ),
    ) -> dict:
        await verify_discord_signature(request)

        interaction = await request.json()

        if interaction["type"] == InteractionType.PING:
            return InteractionResponse(
                type=InteractionCallbackType.PONG, data={}
            ).model_dump()

        elif interaction["type"] == InteractionType.MESSAGE_COMPONENT:
            _log.debug(
                f"New Interaction Data (User: {interaction['member']['user']['username']}): {interaction['data']}"
            )
            channel_id = interaction["channel_id"]
            if channel_id != str(settings.DISCORD_VERIFY_CHANNEL_ID):
                return create_interaction_response(
                    content="승인되지 않은 채널입니다.",
                    ephemeral=True,
                )

            if not check_discord_role(
                interaction["member"]["roles"], settings.DISCORD_VERIFY_ROLE_ID
            ):
                return create_interaction_response(
                    content="권한이 없습니다.",
                    ephemeral=True,
                )

            interaction_context = await discord_requester.build_interaction_context(
                interaction
            )
            return await self.process_interaction(
                interaction_context,
                task_manager=background_tasks,
                requester=discord_requester,
            )
