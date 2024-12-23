import uuid

import aiogoogle.excs
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Query, Depends, status, Request
from fastapi_restful.cbv import cbv
from starlette.responses import RedirectResponse, HTMLResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.websockets import WebSocket

from app.core.deps import get_current_user_entity
from app.entity import User
from app.core.error import ErrorCode
from app.core.response import APIResponse, APIError
from app.service.container import ServiceContainer
from app.service.google import GoogleRequestService
from app.service.session import LoginSessionService, UserSessionService
from app.logger import use_logger
from app.core.redis import settings

router = APIRouter(
    prefix="/auth",
    tags=["Authorization"],
    responses={404: {"description": "Not found"}},
)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URI,
)
_log = use_logger("auth-controller")


@cbv(router)
class AuthController:

    @router.get("/authorization-url")
    @inject
    async def redirect_to_authorization_url(
        self,
        session_id: str = Query(...),
        google_service: GoogleRequestService = Depends(
            Provide[ServiceContainer.google]
        ),
    ) -> RedirectResponse:
        url = await google_service.get_authorization_url(session_id)
        return RedirectResponse(url=url)

    @router.get("/callback")
    @inject
    async def callback(
        self,
        code: str = Query(...),
        session_id: str = Query(alias="state"),
        google_service: GoogleRequestService = Depends(
            Provide[ServiceContainer.google]
        ),
        login_service: LoginSessionService = Depends(
            Provide[ServiceContainer.login_session]
        ),
        user_session: UserSessionService = Depends(
            Provide[ServiceContainer.user_session]
        ),
    ) -> HTMLResponse:
        try:
            credentials = await google_service.fetch_user_credentials(code)
            user_data = await google_service.fetch_user_info(credentials)
        except aiogoogle.excs.HTTPError as e:
            _log.error(f"Google API Error: {e.res}")
            return HTMLResponse(
                content=f"<h1>Error!</h1>"
                f"<p>구글 로그인 오류입니다</p>"
                f"<p>ErrorData: {e.res}</p>"
                f"<p>session id: {session_id}</p>",
            )

        if not await User.filter(email=user_data["email"]).exists():
            user_entity = await User.create(
                id=uuid.uuid4(),
                nickname=user_data["name"],
                email=user_data["email"],
                avatar=user_data["picture"],
            )
        else:
            user_entity = await User.filter(email=user_data["email"]).first()

        if not await login_service.exist_session(session_id=session_id):
            return HTMLResponse(
                content=f"<h1>Error!</h1>"
                f"<p>로그인 세션을 찾을 수 없습니다</p>"
                f"<p>session id: {session_id}</p>",
            )

        await login_service.set_session_user(
            session_id=session_id, user_id=str(user_entity.id)
        )
        if login_service.exist_subscriber(session_id):
            new_access_token = await user_session.create_new_token(str(user_entity.id))
            await login_service.push_token_to_session(session_id, new_access_token)
            await login_service.delete_session(session_id)

        return HTMLResponse(
            content=f"<h1>Success!</h1>"
            f"<p>로그인에 성공했습니다</p>"
            "<p>콘솔로 다시 돌아가세요</p>"
            f"<p>session id: {session_id}</p>",
        )

    @router.get("/login/session")
    @inject
    async def check_session(
        self,
        session_id: str = Query(...),
        login_service: LoginSessionService = Depends(
            Provide[ServiceContainer.login_session]
        ),
        user_session: UserSessionService = Depends(
            Provide[ServiceContainer.user_session]
        ),
    ) -> APIResponse[dict]:
        if not await login_service.exist_session(session_id):
            raise APIError(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.INVALID_SESSION,
                message="Session not found",
            )
        user_id = await login_service.get_session_user_id(session_id)

        if not user_id:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.SESSION_NOT_VERIFIED,
                message="Session not verified",
            )

        new_access_token = await user_session.create_new_token(str(user_id))
        await login_service.delete_session(session_id)
        return APIResponse(
            data={"access_token": new_access_token}, message="Session verified"
        )

    @router.post("/login/session")
    @limiter.limit("20/minute")
    @inject
    async def create_new_session(
        self,
        request: Request,
        login_service: LoginSessionService = Depends(
            Provide[ServiceContainer.login_session]
        ),
    ) -> APIResponse[dict]:
        session_id = await login_service.create_new_session()
        return APIResponse(data={"session_id": session_id}, message="Session created")

    @router.get("/@me")
    @inject
    async def get_current_user(
        self,
        user: User = Depends(get_current_user_entity),
    ) -> APIResponse[dict]:
        return APIResponse(
            data={
                "id": user.id,
                "nickname": user.nickname,
                "email": user.email,
            },
            message="User information",
        )

    @router.post("/logout")
    async def logout(
        self,
        user: User = Depends(get_current_user_entity),
        user_session: UserSessionService = Depends(
            Provide[ServiceContainer.user_session]
        ),
    ) -> APIResponse[dict]:
        await user_session.delete_token(str(user.id))
        return APIResponse(message="Logout success")


@router.websocket("/subscribe")
@inject
async def wait_for_auth(
    websocket: WebSocket,
    session_id: str = Query(...),
    login_service: LoginSessionService = Depends(
        Provide[ServiceContainer.login_session]
    ),
) -> None:
    await websocket.accept()
    if not await login_service.exist_session(session_id):
        return await websocket.close(
            code=status.WS_1003_UNSUPPORTED_DATA,
            reason="Session not found",
        )
    await websocket.send_json({"message": "Waiting for authentication"})
    await login_service.subscribe_session(session_id, websocket)
    while True:
        _ = await websocket.receive_bytes()
