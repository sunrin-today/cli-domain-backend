from dependency_injector import containers, providers

from app.core.websocket import ConnectionManager
from app.service.cloudflare import CloudflareRequestService
from app.service.discord_interaction import DiscordRequester
from app.service.domain import DomainService
from app.service.email import EmailRequesterService
from app.service.google import GoogleRequestService
from app.service.localdb import LocalDBService
from app.service.session import LoginSessionService, UserSessionService


class ServiceContainer(containers.DeclarativeContainer):
    google: GoogleRequestService = providers.Factory(GoogleRequestService)
    websocket = providers.Singleton(ConnectionManager)
    login_session: LoginSessionService = providers.Singleton(
        LoginSessionService, websocket=websocket
    )
    user_session: UserSessionService = providers.Factory(UserSessionService)
    cloudflare: CloudflareRequestService = providers.Factory(CloudflareRequestService)
    localdb: LocalDBService = providers.Singleton(LocalDBService)
    domain: DomainService = providers.Singleton(DomainService)
    discord: DiscordRequester = providers.Factory(DiscordRequester)
    email: EmailRequesterService = providers.Factory(EmailRequesterService)
