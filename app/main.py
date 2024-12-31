from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
from dependency_injector.wiring import inject
from fastapi import FastAPI
from tortoise import generate_config, Tortoise
from tortoise.contrib.fastapi import RegisterTortoise

from app.logger import use_logger
from app.core.config import settings
from app.service.container import ServiceContainer
from app.router import router as api_router

_log = use_logger(__name__)


def modify_cloudflare_error_name(event, hint):
    try:
        if event.get("logger", None) is not None:
            pass
        if "exc_info" in hint:
            exc_type = hint["exc_info"][0]
            if exc_type.__name__ == "APIError":
                if "exception" in event and "values" in event["exception"]:
                    for exception in event["exception"]["values"]:
                        if exception.get("type") == "APIError":
                            error_code = hint["exc_info"][1].error_code.value
                            exception["type"] = f"{exc_type.__name__}_{error_code}"
    except Exception:
        pass
    return event


if settings.SENTRY_DSN and settings.ENVIRONMENT == "production":
    sentry_sdk.init(
        dsn=str(settings.SENTRY_DSN),
        enable_tracing=True,
        before_send=modify_cloudflare_error_name,
        integrations=[],
    )


def bootstrap() -> FastAPI:
    @asynccontextmanager
    @inject
    async def lifespan(
        application: FastAPI,
    ) -> AsyncGenerator[None, None]:
        _log.info("Starting application")
        tortoise_config = generate_config(
            settings.DATABASE_URI,
            app_modules={
                "models": [
                    "app.entity",
                ]
            },
            testing=settings.ENVIRONMENT == "local",
            connection_label="models",
        )
        application.container = container
        _log.info("Container Wiring started")
        container.wire(
            modules=[
                __name__,
                "app.router",
                "app.router.auth",
                "app.router.domain",
                "app.router.discord",
                "app.router.transfer",
            ]
        )
        _log.info("Container Wiring complete")
        async with RegisterTortoise(
            app=application,
            config=tortoise_config,
            generate_schemas=True,
            add_exception_handlers=True,
        ):
            yield
        _log.info("Shutting down application")
        await Tortoise.close_connections()
        _log.info("Application shutdown complete")

    app = FastAPI(
        title="Sunrin Today API",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        debug=settings.ENVIRONMENT == "local",
    )
    return app


container = ServiceContainer()
server = bootstrap()
server.include_router(api_router, prefix=settings.API_V1_STR)
