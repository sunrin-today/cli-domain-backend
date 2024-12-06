from dependency_injector import containers, providers

from app.service.google import GoogleRequestService


class ServiceContainer(containers.DeclarativeContainer):
    google: GoogleRequestService = providers.Factory(GoogleRequestService)
