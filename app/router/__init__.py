from fastapi import APIRouter

from app.core.config import settings
from app.router.auth import router as auth_router
from app.router.domain import router as domain_router
from app.router.discord import router as discord_router

router = APIRouter(
    responses={404: {"description": "Not found"}},
)


@router.get("/")
def root():
    return {"message": f"Hello, {settings.PROJECT_NAME}"}


router.include_router(auth_router)
router.include_router(domain_router)
router.include_router(discord_router)