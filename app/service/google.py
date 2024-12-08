import os

from aiohttp import ClientSession
from app.core.config import settings
from app.logger import use_logger

from aiogoogle import Aiogoogle, auth as aiogoogle_auth

_log = use_logger("google-service")


class GoogleScope:
    BASE_URL = "https://www.googleapis.com/auth"

    def __class_getitem__(cls, key: str) -> str:
        return f"{cls.BASE_URL}/{key}"


class GoogleRequestService:
    def __init__(self) -> None:
        self.__google_credentials = aiogoogle_auth.creds.ClientCreds(
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=[
                GoogleScope["userinfo.email"],
                GoogleScope["userinfo.profile"],
            ],
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
        )
        self._google_client = Aiogoogle(
            client_creds=self.__google_credentials,
        )

    async def get_authorization_url(self, state: str) -> str:
        return self._google_client.oauth2.authorization_url(
            state=state,
            access_type="online",
            include_granted_scopes=True,
            prompt="consent",
        )

    async def fetch_user_credentials(self, code: str) -> dict:
        return await self._google_client.oauth2.build_user_creds(
            grant=code, client_creds=self.__google_credentials
        )

    async def fetch_user_info(self, user_credentials: dict) -> dict:
        return await self._google_client.oauth2.get_me_info(
            user_creds=user_credentials,
        )
