import aiogoogle.excs
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Query, Depends, status
from fastapi_restful.cbv import cbv

from app.core.error import ErrorCode
from app.core.response import APIResponse, APIError
from app.service.container import ServiceContainer
from app.service.google import GoogleRequestService

router = APIRouter(
    prefix="/auth",
    tags=["Authorization"],
    responses={404: {"description": "Not found"}},
)


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
    ) -> APIResponse[dict]:
        url = await google_service.get_authorization_url(session_id)
        return APIResponse(
            data={"authorization_url": url}, message="Authorization URL generated"
        )

    @router.get("/callback")
    @inject
    async def callback(
        self,
        code: str = Query(...),
        state: str = Query(...),
        google_service: GoogleRequestService = Depends(
            Provide[ServiceContainer.google]
        ),
    ) -> APIResponse[dict]:
        try:
            credentials = await google_service.fetch_user_credentials(code)
            user_data = await google_service.fetch_user_info(credentials)
        except aiogoogle.excs.HTTPError as e:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_GOOGLE_CREDENTIALS,
                message="Google API Error",
                error_data={"error": str(e)},
            )
        return APIResponse(data=user_data, message="User credentials fetched")
