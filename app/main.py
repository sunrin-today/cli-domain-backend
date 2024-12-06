from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
from fastapi import FastAPI

from app.logger import use_logger
from app.core.config import settings
from app.service.container import ServiceContainer
from app.router import router as api_router

logger = use_logger(__name__)


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)


def bootstrap() -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        logger.info("Starting application")
        application.container = container
        logger.info("Container Wiring started")
        container.wire(
            modules=[
                __name__,
                "app.router",
                "app.router.auth",
            ]
        )
        logger.info("Container Wiring complete")
        yield
        logger.info("Shutting down application")
        logger.info("Application shutdown complete")

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
