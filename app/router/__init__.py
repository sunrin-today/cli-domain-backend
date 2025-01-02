from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, Depends

from app.router.auth import router as auth_router
from app.router.domain import router as domain_router
from app.router.discord import router as discord_router
from app.router.application import router as application_router
from app.service.container import ServiceContainer
from app.service.domain import DomainService

router = APIRouter(
    responses={404: {"description": "Not found"}},
)


@router.get("/")
def root() -> dict:
    return {"message": f"Hello, Sunrin Today"}


@router.get("/status")
@inject
async def get_status(
    domain_service: DomainService = Depends(Provide[ServiceContainer.domain]),
) -> dict:
    entity_status = await domain_service.get_status()
    return entity_status


router.include_router(auth_router)
router.include_router(domain_router)
router.include_router(discord_router)
router.include_router(application_router)
