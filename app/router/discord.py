import json

from fastapi import APIRouter, Request
from fastapi_restful.cbv import cbv
from fastapi import HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from app.schema.discord import (
    InteractionResponse,
    InteractionCallbackType,
    InteractionType,
    create_interaction_response,
)
from app.logger import use_logger
from app.core.redis import settings
from app.service.discord import check_discord_role

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
        self, interaction: dict
    ) -> InteractionResponse | dict:
        context_id = interaction["data"]["custom_id"]
        command_id, data = context_id.split("@")
        if not self.commands.get(command_id):
            return create_interaction_response(
                content="명령어를 찾을 수 없습니다.",
                ephemeral=True,
            )

        return await self.commands[command_id](interaction=interaction, data=data)

    async def approve_ticket(self, interaction: dict, data: str) -> InteractionResponse:
        return InteractionResponse(
            type=InteractionCallbackType.DEFERRED_CHANNEL_MESSAGE, data={}
        )

    async def reject_ticket(self, interaction: dict, data: str) -> InteractionResponse:
        pass

    @router.post("/interaction")
    async def interaction(
        self,
        request: Request,
    ) -> InteractionResponse:
        await verify_discord_signature(request)

        interaction = await request.json()
        _log.debug(
            f"New Interaction Data (User: {interaction['member']['user']['username']}): {interaction['data']}"
        )

        if interaction["type"] == InteractionType.PING:
            return InteractionResponse(type=InteractionCallbackType.PONG, data={})

        elif interaction["type"] == InteractionType.MESSAGE_COMPONENT:
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

            return await self.process_interaction(interaction)
