"""Authentication routes (Section 9).

Thin per Section 9's "API layer: thin -- validates input shape,
enforces tenant scoping and auth, delegates to the application layer,
shapes the response" -- every route here does exactly that and nothing
more; all actual logic lives in services/auth_service.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.api.deps.auth import get_current_user
from sentinelscan_cloud.api.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenPairResponse,
)
from sentinelscan_cloud.db.session import get_db_session
from sentinelscan_cloud.domain.user import User
from sentinelscan_cloud.services.auth_service import (
    AuthService,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPairResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db_session)) -> TokenPairResponse:
    auth_service = AuthService(session)
    try:
        user = await auth_service.authenticate(email=body.email, password=body.password)
        token_pair = await auth_service.issue_token_pair(user)
    except InvalidCredentialsError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid email or password") from exc

    await session.commit()
    return TokenPairResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in_seconds,
    )


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(body: RefreshRequest, session: AsyncSession = Depends(get_db_session)) -> TokenPairResponse:
    auth_service = AuthService(session)
    try:
        token_pair = await auth_service.refresh(body.refresh_token)
    except InvalidRefreshTokenError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    await session.commit()
    return TokenPairResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in_seconds,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutRequest, session: AsyncSession = Depends(get_db_session)) -> None:
    auth_service = AuthService(session)
    await auth_service.revoke_refresh_token(body.refresh_token)
    await session.commit()


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(user: User = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        organization_id=user.organization_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
    )
