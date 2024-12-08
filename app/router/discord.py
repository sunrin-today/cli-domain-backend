from fastapi import APIRouter, Request
from fastapi_restful.cbv import cbv
from fastapi import HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from app.schema.discord import InteractionResponse, InteractionCallbackType
from app.logger import use_logger
from app.core.redis import settings

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
    signature = request.headers.get('X-Signature-Ed25519')
    timestamp = request.headers.get('X-Signature-Timestamp')
    body = await request.body()

    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Invalid request signature")

    try:
        verify_key.verify(f"{timestamp}{body.decode()}".encode(), bytes.fromhex(signature))
    except BadSignatureError:
        raise HTTPException(status_code=401, detail="Invalid request signature")

@cbv(router)
class DiscordController:

    @router.post("/interaction")
    async def interaction(
        self,
        request: Request,
    ) -> InteractionResponse:
        await verify_discord_signature(request)

        interaction = await request.json()
        print(interaction)

        if interaction['type'] == 1:
            return InteractionResponse(
                type=InteractionCallbackType.PONG,
                data={}
            )

        elif interaction['type'] == 0:
            return InteractionResponse(
                type=InteractionCallbackType.DEFERRED_CHANNEL_MESSAGE,
                data={}
            )

        return InteractionResponse(
            type=InteractionCallbackType.DEFERRED_CHANNEL_MESSAGE,
            data={}
        )


