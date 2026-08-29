from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.api.dependencies import Principal, current_principal, database_session
from mail_control.modules.identity.repository import IdentityRepository
from mail_control.modules.identity.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterTenantRequest,
    TokenPairResponse,
    UserResponse,
)
from mail_control.modules.identity.service import (
    AuthenticationError,
    ConflictError,
    IdentityService,
)
from mail_control.settings import get_settings

router = APIRouter(prefix="/v1/auth", tags=["authentication"])
REFRESH_COOKIE_NAME = "mce_refresh"


def set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.session_absolute_hours * 60 * 60,
        path="/v1/auth",
        secure=settings.is_production,
        httponly=True,
        samesite="lax",
    )


def client_metadata(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    return user_agent, ip_address


def identity_service(session: AsyncSession) -> IdentityService:
    return IdentityService(IdentityRepository(session), get_settings())


@router.post(
    "/register",
    response_model=TokenPairResponse,
    response_model_exclude={"refresh_token"},
    status_code=status.HTTP_201_CREATED,
)
async def register(
    data: RegisterTenantRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(database_session)],
) -> TokenPairResponse:
    try:
        tokens = await identity_service(session).register(data)
        set_refresh_cookie(response, tokens.refresh_token)
        return tokens
    except ConflictError as error:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error


@router.post(
    "/login",
    response_model=TokenPairResponse,
    response_model_exclude={"refresh_token"},
)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(database_session)],
) -> TokenPairResponse:
    user_agent, ip_address = client_metadata(request)
    try:
        tokens = await identity_service(session).login(
            data,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        set_refresh_cookie(response, tokens.refresh_token)
        return tokens
    except AuthenticationError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(error)) from error


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    response_model_exclude={"refresh_token"},
)
async def refresh(
    data: RefreshRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(database_session)],
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> TokenPairResponse:
    user_agent, ip_address = client_metadata(request)
    try:
        token = data.refresh_token or refresh_cookie
        if not token:
            raise AuthenticationError("invalid refresh token")
        tokens = await identity_service(session).rotate_refresh_token(
            token,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        set_refresh_cookie(response, tokens.refresh_token)
        return tokens
    except AuthenticationError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(error)) from error


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    data: LogoutRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(database_session)],
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> Response:
    token = data.refresh_token or refresh_cookie
    if token:
        await identity_service(session).logout(token)
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/v1/auth",
        secure=get_settings().is_production,
        httponly=True,
        samesite="lax",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
async def me(
    principal: Annotated[Principal, Depends(current_principal)],
) -> UserResponse:
    return UserResponse.model_validate(principal.user)
