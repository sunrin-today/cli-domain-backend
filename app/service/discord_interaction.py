import contextlib
from typing import ClassVar, Any

from aiohttp import ClientSession
from sentry_sdk import capture_exception
from discord import Embed, ui, ButtonStyle, Interaction, Client, Intents, Color
from datetime import datetime

from app.core.config import settings
from app.core.error import ErrorCode
from app.core.response import APIError
from app.logger import use_logger

from app.entity import User as UserEntity

_http_log = use_logger("aiohttp-request")
_discord_log = use_logger("discord-request-service")


class TicketControlDiscordComponent(ui.View):
    @ui.button(label="승인", style=ButtonStyle.green)
    async def approve(self, button: ui.Button, interaction: Interaction): ...

    @ui.button(label="거절", style=ButtonStyle.red)
    async def reject(self, button: ui.Button, interaction: Interaction): ...


def build_ticket_message(
    domain_name: str, user: UserEntity, record_value: dict, ticket_id: str
) -> dict:
    value_string = "\n".join(f"{key}: {value}" for key, value in record_value.items())
    embed = (
        Embed(
            title=f"{domain_name} 도메인 등록 요청",
            description=f"```yaml\n{value_string}\n```",
            color=Color.from_str("#00FFFF"),
        )
        .set_author(name=f"{user.nickname} ({user.email})", icon_url=user.avatar)
        .set_footer(text=f"Ticket ID: {ticket_id}")
    )
    embed.timestamp = datetime.now()
    component = TicketControlDiscordComponent()

    return {
        "embed": embed,
        "view": component,
    }


class DiscordRequester:
    def __init__(self) -> None:
        self._client = Client(
            intents=Intents.none(),
        )
        self._is_login = False

    async def send_ticket_message(
        self, domain_name: str, user: UserEntity, record_value: dict, ticket_id: str
    ) -> None:
        if not self._is_login:
            await self._client.login(settings.DISCORD_BOT_TOKEN)
            self._is_login = True
        message = build_ticket_message(domain_name, user, record_value, ticket_id)
        channel = await self._client.fetch_channel(settings.DISCORD_VERIFY_CHANNEL_ID)
        await channel.send(**message)
