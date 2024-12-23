import secrets
from typing import Literal, Any, Annotated
from pydantic import (
    field_validator,
    BeforeValidator,
)

from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_string_list(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)

    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    SERVER_PORT: int
    SENTRY_DSN: str | None = None

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str

    DATABASE_URI: str
    REDIS_URI: str

    CLOUDFLARE_API_TOKEN: str
    DISCORD_PUBLIC_KEY: str
    DISCORD_BOT_TOKEN: str
    DISCORD_VERIFY_CHANNEL_ID: str
    DISCORD_VERIFY_ROLE_ID: str

    USER_DOMAIN_MAXIMUM: int

    @staticmethod
    @field_validator("SERVER_PORT")
    def check_port_range(value: int):
        if not 0 < value < 65536:
            raise ValueError("SERVER_PORT number must be between 1 and 65535")
        return value


settings = Settings()
