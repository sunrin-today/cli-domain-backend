from typing import Any, Sequence, Union

from discord.abc import MISSING
from discord.ui import View
from discord.webhook.async_ import interaction_message_response_params
from discord import (
    Embed,
    ui,
    ButtonStyle,
    Interaction,
    Client,
    Intents,
    Color,
    File,
    AllowedMentions,
    Poll,
    InteractionResponseType,
    MessageFlags,
    Attachment,
)
from datetime import datetime

from app.core.config import settings
from app.logger import use_logger

from app.entity import User as UserEntity
from app.entity import Domain as DomainEntity
from app.entity import DomainTicket as DomainTicketEntity

_http_log = use_logger("aiohttp-request")
_discord_log = use_logger("discord-request-service")


class TicketRespondDiscordComponent(ui.View):
    def __init__(self, approve: bool, ticket_id: str) -> None:
        super().__init__(timeout=None)
        self.approve = approve
        self.ticket_id = ticket_id
        self.add_item(
            ui.Button(
                label=(
                    "승인을 취소하려면 /거절 명령어를 사용하세요"
                    if approve
                    else "거절을 취소하려면 /승인 명령어를 사용하세요"
                ),
                style=ButtonStyle.gray,
                disabled=True,
            )
        )

    @classmethod
    def success(cls, ticket_id: str) -> "TicketRespondDiscordComponent":
        self = cls(approve=True, ticket_id=ticket_id)
        return self

    @classmethod
    def reject(cls, ticket_id: str) -> "TicketRespondDiscordComponent":
        return cls(approve=False, ticket_id=ticket_id)


class TicketControlDiscordComponent(ui.View):
    def __init__(self, ticket_id: str):
        super().__init__(timeout=None)
        approve_button = ui.Button(
            label="승인",
            style=ButtonStyle.green,
            custom_id=f"approve@{ticket_id}",
        )
        reject_button = ui.Button(
            label="거절",
            style=ButtonStyle.red,
            custom_id=f"reject@{ticket_id}",
        )
        self.add_item(
            approve_button,
        )
        self.add_item(
            reject_button,
        )


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
    component = TicketControlDiscordComponent(ticket_id)

    return {
        "embed": embed,
        "view": component,
    }


class InteractionRestResponse:

    @staticmethod
    def send_message(
        content: Any | None = None,
        *,
        embed: Embed = MISSING,
        embeds: Sequence[Embed] = MISSING,
        file: File = MISSING,
        files: Sequence[File] = MISSING,
        view: View = MISSING,
        ephemeral: bool = False,
        poll: Poll = MISSING,
    ) -> dict:
        flag = MessageFlags()
        if ephemeral:
            flag.value = 64
        else:
            flag.value = 0
        params = interaction_message_response_params(
            type=InteractionResponseType.channel_message.value,
            content=content,
            tts=False,
            embeds=embeds,
            embed=embed,
            file=file,
            files=files,
            previous_allowed_mentions=AllowedMentions.none(),
            allowed_mentions=None,
            flags=flag,
            view=view,
            poll=poll,
        )
        return params.payload

    @staticmethod
    def edit_message(
        *,
        content: Any | None = MISSING,
        embed: Embed | None = MISSING,
        embeds: Sequence[Embed] = MISSING,
        attachments: Sequence[Union[Attachment, File]] = MISSING,
        view: View | None = MISSING,
    ) -> dict:
        params = interaction_message_response_params(
            type=InteractionResponseType.message_update.value,
            content=content,
            embed=embed,
            embeds=embeds,
            view=view,
            attachments=attachments,
            previous_allowed_mentions=AllowedMentions.none(),
            allowed_mentions=None,
            flags=MISSING,
        )
        return params.payload


class DiscordRequester:
    def __init__(self) -> None:
        self._client = Client(
            intents=Intents.none(),
        )
        self._is_login = False

    @property
    def response(self) -> InteractionRestResponse:
        return InteractionRestResponse()

    async def login(self) -> None:
        await self._client.login(settings.DISCORD_BOT_TOKEN)
        self._is_login = True

    async def _login_check(self) -> None:
        if not self._is_login:
            await self.login()

    async def send_ticket_message(
        self, domain_name: str, user: UserEntity, record_value: dict, ticket_id: str
    ) -> None:
        await self._login_check()
        message = build_ticket_message(domain_name, user, record_value, ticket_id)
        channel = await self._client.fetch_channel(settings.DISCORD_VERIFY_CHANNEL_ID)
        await channel.send(**message)

    async def build_interaction_context(self, data: dict) -> Interaction:
        await self._login_check()
        return Interaction(data=data, state=getattr(self._client, "_connection"))

    async def create_log_new_domain(
        self,
        user: UserEntity,
        ticket: DomainTicketEntity,
        domain: DomainEntity,
        data: dict,
    ) -> None:
        await self._login_check()
        channel = await self._client.fetch_channel(settings.DISCORD_LOG_CHANNEL_ID)
        value_string = "\n".join(f"{key}: {value}" for key, value in data.items())
        embed = Embed(
            title=f"[새 도메인 등록] {domain.name}",
            description=f"```yaml\n{value_string}\n```",
            color=Color.from_str("#00FF00"),
        ).set_author(name=f"{user.nickname} ({user.email})", icon_url=user.avatar)
        embed.timestamp = datetime.now()
        await channel.send(
            content=f"[새 도메인 등록] 도메인 ID=``{domain.id}``\n"
            f"티켓 ID=``{ticket.id}``",
            embed=embed,
        )

    async def create_log_rejected_domain(
        self,
        user: UserEntity,
        ticket: DomainTicketEntity,
        data: dict,
    ) -> None:
        await self._login_check()
        channel = await self._client.fetch_channel(settings.DISCORD_LOG_CHANNEL_ID)
        value_string = "\n".join(f"{key}: {value}" for key, value in data.items())
        embed = Embed(
            title=f"[도메인 거절] {ticket.name}",
            description=f"```yaml\n{value_string}\n```",
            color=Color.from_str("#FF0000"),
        ).set_author(name=f"{user.nickname} ({user.email})", icon_url=user.avatar)
        embed.timestamp = datetime.now()
        await channel.send(
            content=f"[도메인 거절] 티켓 ID=``{ticket.id}``",
            embed=embed,
        )

    async def create_log_service_error(
        self,
        user: UserEntity,
        error_name: str,
        description: str,
        data: dict,
    ) -> None:
        await self._login_check()
        channel = await self._client.fetch_channel(settings.DISCORD_LOG_CHANNEL_ID)
        embed = Embed(
            title=f"[서비스 에러] {error_name}",
            description=f"{description}\n```json\n{data}\n```",
            color=Color.from_str("#FF0000"),
        ).set_author(name=f"{user.nickname} ({user.email})", icon_url=user.avatar)
        embed.timestamp = datetime.now()
        await channel.send(
            content=f"[서비스 에러] {error_name}",
            embed=embed,
        )

    async def create_log_update_domain(
        self,
        user: UserEntity,
        domain: DomainEntity,
        data: dict,
    ) -> None:
        await self._login_check()
        channel = await self._client.fetch_channel(settings.DISCORD_LOG_CHANNEL_ID)
        value_string = "\n".join(f"{key}: {value}" for key, value in data.items())
        embed = Embed(
            title=f"[도메인 업데이트] {domain.name}",
            description=f"```yaml\n{value_string}\n```",
            color=Color.from_str("#00FF00"),
        ).set_author(name=f"{user.nickname} ({user.email})", icon_url=user.avatar)
        embed.timestamp = datetime.now()
        await channel.send(
            content=f"[도메인 업데이트] 도메인 ID=``{domain.id}``\n"
            f"도메인 Cloudflare Record ID = ``{domain.record_id}``",
            embed=embed,
        )

    async def create_log_close_ticket(
        self,
        user: UserEntity,
        ticket: DomainTicketEntity,
    ) -> None:
        await self._login_check()
        channel = await self._client.fetch_channel(settings.DISCORD_LOG_CHANNEL_ID)
        embed = Embed(
            title=f"[티켓 종료] {ticket.name}",
            description=f"사용자가 티켓을 종료함.",
            color=Color.from_str("#00FF00"),
        ).set_author(name=f"{user.nickname} ({user.email})", icon_url=user.avatar)
        embed.timestamp = datetime.now()
        await channel.send(
            content=f"[티켓 종료] 티켓 ID=``{ticket.id}``",
            embed=embed,
        )

    async def create_log_user_create(self, email: str, name: str, avatar: str) -> None:
        await self._login_check()
        channel = await self._client.fetch_channel(settings.DISCORD_LOG_CHANNEL_ID)
        embed = Embed(
            title=f"[유저 생성] {name}",
            description=f"사용자가 생성됨.",
            color=Color.from_str("#00FF00"),
        ).set_author(name=f"{name} ({email})", icon_url=avatar)
        embed.timestamp = datetime.now()
        await channel.send(
            content=f"[유저 생성] {name}",
            embed=embed,
        )

    async def create_log_refresh_session(self, user: UserEntity) -> None:
        await self._login_check()
        channel = await self._client.fetch_channel(settings.DISCORD_LOG_CHANNEL_ID)
        embed = Embed(
            title=f"[세션 갱신] {user.nickname}",
            description=f"세션 갱신됨.\n",
            color=Color.from_str("#00FF00"),
        ).set_author(name=f"{user.nickname} ({user.email})", icon_url=user.avatar)
        embed.timestamp = datetime.now()
        await channel.send(
            content=f"[세션 갱신] {user.nickname}",
            embed=embed,
        )

    async def create_log_delete_domain(
        self, user: UserEntity, domain: DomainEntity
    ) -> None:
        await self._login_check()
        channel = await self._client.fetch_channel(settings.DISCORD_LOG_CHANNEL_ID)
        embed = Embed(
            title=f"[도메인 삭제] {domain.name}",
            description=f"도메인 삭제됨. {domain.name}이 삭제됨.",
            color=Color.from_str("#FF0000"),
        ).set_author(name=f"{user.nickname} ({user.email})", icon_url=user.avatar)
        embed.timestamp = datetime.now()
        await channel.send(
            content=f"[도메인 삭제]",
            embed=embed,
        )

    async def create_log_transfer_invite(
        self, user: UserEntity, domain: DomainEntity, target_user_email: str
    ) -> None:
        await self._login_check()
        channel = await self._client.fetch_channel(settings.DISCORD_LOG_CHANNEL_ID)
        embed = Embed(
            title=f"[도메인 이전 링크 생성] {domain.name}",
            description=f" {domain.name} 도메인을 {target_user_email}에게 이전할 수 있는 링크 생성됨.",
            color=Color.from_str("#FF0000"),
        ).set_author(name=f"{user.nickname} ({user.email})", icon_url=user.avatar)
        embed.timestamp = datetime.now()
        await channel.send(
            content=f"[도메인 이전 링크 생성]",
            embed=embed,
        )

    async def create_log_transfer_domain(
        self, user: UserEntity, domain: DomainEntity, target_user_email: str
    ) -> None:
        await self._login_check()
        channel = await self._client.fetch_channel(settings.DISCORD_LOG_CHANNEL_ID)
        embed = Embed(
            title=f"[도메인 이전] {domain.name}",
            description=f"도메인 이전됨. {domain.name}이 {target_user_email}로 이전됨.",
            color=Color.from_str("#FF0000"),
        ).set_author(name=f"{user.nickname} ({user.email})", icon_url=user.avatar)
        embed.timestamp = datetime.now()
        await channel.send(
            content=f"[도메인 이전]",
            embed=embed,
        )
