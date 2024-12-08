import redis.exceptions
from dependency_injector.wiring import Provide, inject

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.entity.user import User as UserEntity
from app.logger import use_logger
from app.service.container import ServiceContainer
from app.service.session import UserSessionService


security = HTTPBearer(scheme_name="Access Token")
_log = use_logger("auth-deps")


def get_user_token(request: Request) -> str:
    header_value = request.headers.get("Authorization")
    return header_value.split(" ")[1]


@inject
async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_session: UserSessionService = Depends(Provide[ServiceContainer.user_session]),
) -> str:
    try:
        token = credentials.credentials
        if await user_session.exist_token(token) is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )

        user_id = await user_session.get_user_id(token)

        return user_id
    except redis.exceptions.RedisError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@inject
async def get_current_user_entity(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_session: UserSessionService = Depends(Provide[ServiceContainer.user_session]),
) -> UserEntity | None:
    try:
        token = credentials.credentials
        if await user_session.exist_token(token) is None:
            _log.error("Invalid authentication token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )

        _log.info(f"Token: {token}")

        user_id = await user_session.get_user_id(token)
        _log.info(f"User ID: {user_id}")

        if not await UserEntity.exists(id=str(user_id)):
            _log.error("User not found")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )

        await user_session.update_token(token)

        return await UserEntity.get(id=user_id)
    except redis.exceptions.RedisError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
