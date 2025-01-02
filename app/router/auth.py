import uuid

import aiogoogle.excs
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Query, Depends, status, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_restful.cbv import cbv
from starlette.responses import RedirectResponse, HTMLResponse
from starlette.websockets import WebSocketDisconnect
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.websockets import WebSocket

from app.core.deps import get_current_user_entity, get_user_token
from app.core.string import (
    parse_application_url,
    create_application_redirect_url,
    create_application_reject_url,
)
from app.entity import User
from app.core.error import ErrorCode
from app.core.response import APIResponse, APIError
from app.service.container import ServiceContainer
from app.service.email import EmailRequesterService
from app.service.google import GoogleRequestService
from app.service.session import LoginSessionService, UserSessionService
from app.service.discord_interaction import DiscordRequester
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
templates = Jinja2Templates(directory="template")
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

    @router.get("/app/rejected")
    async def app_rejected(
        self, request: Request, name: str = Query(...)
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "status": "failed",
                "message": "애플리케이션 요청이 거절됨.",
                "detail": f"사용자가 {name} 애플리케이션 요청을 거절했습니다.",
                "login_data": f"AppName: {name}",
            },
        )

    @router.get("/callback")
    @inject
    async def callback(
        self,
        request: Request,
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
        discord_service: DiscordRequester = Depends(Provide[ServiceContainer.discord]),
        email_service: EmailRequesterService = Depends(Provide[ServiceContainer.email]),
    ) -> HTMLResponse:
        try:
            credentials = await google_service.fetch_user_credentials(code)
            user_data = await google_service.fetch_user_info(credentials)
        except aiogoogle.excs.HTTPError as e:
            _log.error(f"Google API Error: {e.res}")
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={
                    "status": "failed",
                    "message": f"구글 로그인 오류입니다.",
                    "detail": str(e.res),
                    "login_data": session_id,
                },
            )

        if not await User.filter(email=user_data["email"]).exists():
            user_entity = await User.create(
                id=uuid.uuid4(),
                nickname=user_data["name"],
                email=user_data["email"],
                avatar=user_data["picture"],
            )
            await discord_service.create_log_user_create(
                email=user_data["email"],
                name=user_data["name"],
                avatar=user_data["picture"],
            )
            await email_service.send_welcome_email(
                to_email=user_data["email"],
                name=user_data["name"],
            )
        else:
            user_entity = await User.filter(email=user_data["email"]).first()

        if session_id.startswith("@"):
            parsed_data = parse_application_url(session_id)
            if not parsed_data["application"] in ["vercel", "transfer"]:
                return templates.TemplateResponse(
                    request=request,
                    name="login.html",
                    context={
                        "status": "failed",
                        "message": f"애플리케이션 로그인 오류",
                        "detail": "잘못된 application url입니다.",
                        "login_data": session_id,
                    },
                )
            new_access_token = await user_session.create_new_token(str(user_entity.id))
            temporary_application_only_id = (
                "App" + parsed_data["application"].capitalize() + str(uuid.uuid4())
            )
            await login_service.push_token_to_session(
                temporary_application_only_id, new_access_token
            )
            parsed_data["parameters"].update({"token": new_access_token})
            redirect_url = create_application_redirect_url(
                base_url=settings.BACKEND_HOST,
                application=parsed_data["application"],
                route=parsed_data["route"],
                params=parsed_data["parameters"],
            )
            application_permission = {
                "vercel": [
                    {
                        "icon": "fas fa-user",
                        "name": "프로필 정보 읽기",
                        "content": "이름, 이메일, 프로필 사진을 읽습니다.",
                    },
                    {
                        "icon": "fa-solid fa-tower-cell",
                        "name": "도메인 관리",
                        "content": "자동으로 도메인을 연결합니다.",
                    },
                    {
                        "icon": "fa-solid fa-circle-nodes",
                        "name": "Vercel 계정으로 로그인",
                        "content": "Vercel 계정에 접근하여 도메인을 자동으로 인증받습니다.",
                    },
                ],
                "transfer": [
                    {
                        "icon": "fas fa-user",
                        "name": "프로필 정보 읽기",
                        "content": "도메인 이전 대상 사용자가 맞는지 확인합니다.",
                    },
                    {
                        "icon": "fa-solid fa-tower-cell",
                        "name": "도메인 관리",
                        "content": "다른 유저의 도메인을 내 계정으로 이전합니다.",
                    },
                ],
            }
            return templates.TemplateResponse(
                request=request,
                name="app-login.html",
                context={
                    "name": parsed_data["application"].capitalize(),
                    "permissions": application_permission[parsed_data["application"]],
                    "accept_url": redirect_url,
                    "reject_url": create_application_reject_url(
                        base_url=settings.BACKEND_HOST,
                        app_name=parsed_data["application"],
                    ),
                },
            )

        if not await login_service.exist_session(session_id=session_id):
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={
                    "status": "failed",
                    "message": f"알 수 없는 세션",
                    "detail": "로그인 세션을 찾을 수 없습니다.",
                    "login_data": session_id,
                },
            )

        await login_service.set_session_user(
            session_id=session_id, user_id=str(user_entity.id)
        )
        await discord_service.create_log_refresh_session(user=user_entity)
        if login_service.exist_subscriber(session_id):
            new_access_token = await user_session.create_new_token(str(user_entity.id))
            await login_service.push_token_to_session(session_id, new_access_token)
            await login_service.delete_session(session_id)
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "status": "success",
                "message": f"로그인에 성공했습니다",
                "detail": "콘솔로 다시 돌아가세요",
                "login_data": session_id,
            },
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
    @inject
    async def logout(
        self,
        token: str = Depends(get_user_token),
        user_session: UserSessionService = Depends(
            Provide[ServiceContainer.user_session]
        ),
    ) -> APIResponse[dict]:
        await user_session.delete_token(token)
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
    try:
        while True:
            _ = await websocket.receive_bytes()
    except WebSocketDisconnect:
        await websocket.close()
